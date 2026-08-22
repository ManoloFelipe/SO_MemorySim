import random
from django.db import transaction
from .models import Process, SimulationState, SimulationLog
from .memory_manager import MemoryManager

SYSTEM_PROCESS_NAMES = [
    "WebBrowser", "DB_Server", "Compiler", "AudioPlayer", "VideoEncoder",
    "TextEditor", "GameEngine", "AnalyticsWorker", "ImageProcessor", "NetworkDaemon",
    "SecurityScanner", "CloudSync", "DataBackup", "RenderPipeline", "APIGateway"
]


class SimulationEngine:
    """Core simulation orchestrator for RAM memory management and process scheduling."""

    def __init__(self):
        self.state = SimulationState.get_state()
        self.memory_mgr = MemoryManager(total_memory=self.state.total_memory)

    def log_event(self, event_type: str, message: str, tick: int = None):
        """Creates a timestamped audit log entry."""
        if tick is None:
            tick = self.state.current_tick
        return SimulationLog.objects.create(
            tick=tick,
            event_type=event_type,
            message=message
        )

    def get_running_processes(self):
        """Returns QuerySet of currently running processes with allocated memory."""
        return Process.objects.filter(status='RUNNING').order_by('memory_start_address')

    def get_waiting_processes(self):
        """Returns QuerySet of queued processes in FIFO order."""
        return Process.objects.filter(status='WAITING').order_by('queue_order')

    def get_completed_processes(self):
        """Returns QuerySet of completed or terminated processes."""
        return Process.objects.filter(status__in=['COMPLETED', 'TERMINATED']).order_by('-finished_at_tick')

    @transaction.atomic
    def create_process(self, name: str = None, required_memory: int = 128, duration: int = 10, pid: int = None):
        """
        Creates a new process. If sufficient RAM is available, admits it immediately into memory;
        otherwise places it in the waiting queue.
        """
        if pid is None or Process.objects.filter(pid=pid).exists():
            pid = SimulationState.next_pid()

        if not name or not name.strip():
            random_name = random.choice(SYSTEM_PROCESS_NAMES)
            name = f"{random_name}_{pid}"
        else:
            name = name.strip()

        required_memory = max(16, min(self.state.total_memory, int(required_memory)))
        duration = max(1, int(duration))

        process = Process(
            pid=pid,
            name=name,
            required_memory=required_memory,
            duration=duration,
            remaining_time=duration,
            status='WAITING',
            color=Process.get_random_color(),
            created_at_tick=self.state.current_tick
        )

        # Try to allocate RAM immediately
        running_procs = list(self.get_running_processes())
        allocated, start_addr, end_addr = self.memory_mgr.allocate(
            required_memory, running_procs, self.state.algorithm
        )

        if allocated:
            process.status = 'RUNNING'
            process.memory_start_address = start_addr
            process.memory_end_address = end_addr
            process.started_at_tick = self.state.current_tick
            process.save()

            self.log_event(
                'PROCESS_ADMITTED',
                f"Proceso PID {pid} ('{name}') asignado a RAM: [{start_addr} MB - {end_addr} MB] ({required_memory} MB, duración {duration}s)."
            )
        else:
            process.save()
            stats = self.memory_mgr.get_memory_stats(running_procs)
            self.log_event(
                'PROCESS_QUEUED',
                f"Proceso PID {pid} ('{name}') colocado en COLA DE ESPERA. Requiere {required_memory} MB (RAM libre total: {stats['free_mb']} MB, bloque continuo máx: {stats['max_contiguous_free_mb']} MB)."
            )

        return process

    @transaction.atomic
    def process_waiting_queue(self):
        """
        Iterates over the waiting queue (FIFO) and allocates memory to any processes
        that now fit into available RAM blocks.
        """
        waiting_procs = list(self.get_waiting_processes())
        promoted_count = 0

        for proc in waiting_procs:
            running_procs = list(self.get_running_processes())
            allocated, start_addr, end_addr = self.memory_mgr.allocate(
                proc.required_memory, running_procs, self.state.algorithm
            )

            if allocated:
                proc.status = 'RUNNING'
                proc.memory_start_address = start_addr
                proc.memory_end_address = end_addr
                proc.started_at_tick = self.state.current_tick
                proc.save()
                promoted_count += 1

                self.log_event(
                    'PROCESS_ADMITTED',
                    f"Proceso PID {proc.pid} ('{proc.name}') promovido de la COLA a RAM: [{start_addr} MB - {end_addr} MB] ({proc.required_memory} MB)."
                )

        return promoted_count

    @transaction.atomic
    def tick(self):
        """
        Executes one clock tick (1 second of simulation time):
        1. Advances global clock tick.
        2. Decrements remaining time for all RUNNING processes concurrently.
        3. Frees memory for any process that finished.
        4. Admits waiting processes into newly freed RAM.
        """
        self.state.current_tick += 1
        self.state.save()

        running_procs = list(self.get_running_processes())
        freed_memory_total = 0
        finished_procs = []

        for proc in running_procs:
            proc.remaining_time -= 1

            if proc.remaining_time <= 0:
                # Process finished execution!
                proc.remaining_time = 0
                proc.status = 'COMPLETED'
                proc.finished_at_tick = self.state.current_tick
                freed_mb = proc.required_memory
                start_mb = proc.memory_start_address
                end_mb = proc.memory_end_address

                # Release memory block
                proc.memory_start_address = None
                proc.memory_end_address = None
                proc.save()

                freed_memory_total += freed_mb
                finished_procs.append(proc)

                self.log_event(
                    'PROCESS_FINISHED',
                    f"Proceso PID {proc.pid} ('{proc.name}') finalizó con éxito. Liberados {freed_mb} MB [{start_mb} MB - {end_mb} MB]."
                )
            else:
                proc.save()

        # If memory was freed, or if there is available space, schedule waiting processes
        promoted = self.process_waiting_queue()

        return {
            'tick': self.state.current_tick,
            'finished_count': len(finished_procs),
            'freed_mb': freed_memory_total,
            'promoted_count': promoted
        }

    @transaction.atomic
    def terminate_process(self, pid: int):
        """
        Manually kills a process (either RUNNING or WAITING), releasing its memory if running.
        """
        try:
            proc = Process.objects.get(pid=pid)
        except Process.DoesNotExist:
            return False, "Proceso no encontrado"

        if proc.status in ['COMPLETED', 'TERMINATED']:
            return False, "El proceso ya no está activo"

        was_running = (proc.status == 'RUNNING')
        freed_mb = proc.required_memory
        start_mb = proc.memory_start_address
        end_mb = proc.memory_end_address

        proc.status = 'TERMINATED'
        proc.finished_at_tick = self.state.current_tick
        proc.memory_start_address = None
        proc.memory_end_address = None
        proc.save()

        if was_running:
            self.log_event(
                'PROCESS_TERMINATED',
                f"Proceso PID {proc.pid} ('{proc.name}') terminado por el usuario. Liberados {freed_mb} MB [{start_mb} MB - {end_mb} MB]."
            )
            # Process queue to let waiting processes take the freed RAM
            self.process_waiting_queue()
        else:
            self.log_event(
                'PROCESS_TERMINATED',
                f"Proceso PID {proc.pid} ('{proc.name}') cancelado de la cola de espera."
            )

        return True, "Proceso terminado con éxito"

    @transaction.atomic
    def reset_simulation(self):
        """Resets the simulation to its initial state."""
        Process.objects.all().delete()
        SimulationLog.objects.all().delete()

        self.state.current_tick = 0
        self.state.is_running = False
        self.state.last_pid = 1000
        self.state.save()

        self.log_event('INFO', "Simulador reiniciado. 1024 MB de memoria RAM disponible.")
        return True

    def set_running_state(self, is_running: bool, speed_ms: int = None, algorithm: str = None):
        """Updates simulation execution toggle and parameters."""
        self.state.is_running = is_running
        if speed_ms is not None:
            self.state.speed_ms = int(speed_ms)
        if algorithm is not None and algorithm in ['FIRST_FIT', 'BEST_FIT', 'WORST_FIT']:
            self.state.algorithm = algorithm
        self.state.save()
        return self.state

    def generate_batch(self, count: int = 5, profile: str = 'mixed'):
        """
        Generates a batch of test processes with varying RAM and duration requirements.
        """
        count = max(1, min(20, int(count)))
        created_procs = []

        presets = {
            'light': {'mem_range': [32, 64, 96, 128], 'dur_range': (3, 8)},
            'balanced': {'mem_range': [64, 128, 192, 256, 320], 'dur_range': (5, 15)},
            'heavy': {'mem_range': [256, 384, 512, 768], 'dur_range': (8, 25)},
            'mixed': {'mem_range': [32, 64, 128, 256, 384, 512], 'dur_range': (4, 18)},
        }

        cfg = presets.get(profile, presets['mixed'])

        for _ in range(count):
            mem = random.choice(cfg['mem_range'])
            dur = random.randint(*cfg['dur_range'])
            proc = self.create_process(
                name=None,
                required_memory=mem,
                duration=dur
            )
            created_procs.append(proc)

        return created_procs

    def get_full_status(self):
        """
        Returns full state dictionary for the frontend dashboard and API polling.
        """
        running = list(self.get_running_processes())
        waiting = list(self.get_waiting_processes())
        completed = list(self.get_completed_processes()[:15])
        logs = list(SimulationLog.objects.all()[:30])

        memory_stats = self.memory_mgr.get_memory_stats(running)

        def serialize_process(p):
            return {
                'pid': p.pid,
                'name': p.name,
                'required_memory': p.required_memory,
                'duration': p.duration,
                'remaining_time': p.remaining_time,
                'progress': p.progress_percentage,
                'status': p.status,
                'status_display': p.get_status_display(),
                'color': p.color,
                'memory_start_address': p.memory_start_address,
                'memory_end_address': p.memory_end_address,
                'created_at_tick': p.created_at_tick,
                'started_at_tick': p.started_at_tick,
                'finished_at_tick': p.finished_at_tick,
            }

        return {
            'state': {
                'current_tick': self.state.current_tick,
                'is_running': self.state.is_running,
                'speed_ms': self.state.speed_ms,
                'algorithm': self.state.algorithm,
                'total_memory': self.state.total_memory,
            },
            'memory': memory_stats,
            'counts': {
                'running': len(running),
                'waiting': len(waiting),
                'completed': Process.objects.filter(status='COMPLETED').count(),
                'terminated': Process.objects.filter(status='TERMINATED').count(),
                'total': Process.objects.count(),
            },
            'running_processes': [serialize_process(p) for p in running],
            'waiting_processes': [serialize_process(p) for p in waiting],
            'completed_processes': [serialize_process(p) for p in completed],
            'logs': [
                {
                    'id': log.id,
                    'tick': log.tick,
                    'event_type': log.event_type,
                    'event_type_display': log.get_event_type_display(),
                    'message': log.message,
                    'created_at': log.created_at.strftime('%H:%M:%S')
                }
                for log in logs
            ]
        }
