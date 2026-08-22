import random
from django.db import models


class SimulationState(models.Model):
    """Singleton model representing global simulation parameters and state."""
    total_memory = models.IntegerField(default=1024, help_text="Total RAM in MB (1 GB = 1024 MB)")
    current_tick = models.IntegerField(default=0, help_text="Elapsed time in seconds (clock ticks)")
    is_running = models.BooleanField(default=False, help_text="Whether auto-simulation is currently active")
    speed_ms = models.IntegerField(default=1000, help_text="Auto-tick interval in ms")
    algorithm = models.CharField(
        max_length=20,
        choices=[
            ('FIRST_FIT', 'First Fit'),
            ('BEST_FIT', 'Best Fit'),
            ('WORST_FIT', 'Worst Fit'),
        ],
        default='FIRST_FIT'
    )
    last_pid = models.IntegerField(default=1000, help_text="Counter for generating unique PIDs")

    @classmethod
    def get_state(cls):
        state, _ = cls.objects.get_or_create(id=1)
        return state

    @classmethod
    def next_pid(cls):
        state = cls.get_state()
        state.last_pid += 1
        state.save()
        return state.last_pid

    def __str__(self):
        return f"SimState(Tick: {self.current_tick}s, Running: {self.is_running})"


# Palette of vibrant, distinguishable colors for process memory visualization
PROCESS_PALETTE = [
    '#3B82F6', # Blue
    '#10B981', # Emerald
    '#F59E0B', # Amber
    '#EC4899', # Pink
    '#8B5CF6', # Purple
    '#06B6D4', # Cyan
    '#F97316', # Orange
    '#14B8A6', # Teal
    '#6366F1', # Indigo
    '#EF4444', # Rose Red
    '#84CC16', # Lime
    '#D946EF', # Fuchsia
]


class Process(models.Model):
    """Represents a process running or waiting in the operating system simulator."""
    STATUS_CHOICES = [
        ('WAITING', 'En Espera'),
        ('RUNNING', 'En Ejecución'),
        ('COMPLETED', 'Completado'),
        ('TERMINATED', 'Terminado'),
    ]

    pid = models.IntegerField(unique=True, help_text="Unique Process ID")
    name = models.CharField(max_length=120, help_text="Descriptive Process Name")
    required_memory = models.IntegerField(help_text="RAM required in MB")
    duration = models.IntegerField(help_text="Total execution time in seconds")
    remaining_time = models.IntegerField(help_text="Remaining execution time in seconds")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='WAITING')
    color = models.CharField(max_length=15, default='#3B82F6')

    # Memory allocation addresses (in MB offset from 0 to 1024)
    memory_start_address = models.IntegerField(null=True, blank=True)
    memory_end_address = models.IntegerField(null=True, blank=True)

    # Simulation timeline metrics
    created_at_tick = models.IntegerField(default=0)
    started_at_tick = models.IntegerField(null=True, blank=True)
    finished_at_tick = models.IntegerField(null=True, blank=True)
    queue_order = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['queue_order']

    def __str__(self):
        return f"PID {self.pid} - {self.name} ({self.required_memory} MB, {self.status})"

    @property
    def progress_percentage(self):
        if self.duration <= 0:
            return 100
        elapsed = self.duration - self.remaining_time
        return max(0, min(100, int((elapsed / self.duration) * 100)))

    @classmethod
    def get_random_color(cls):
        return random.choice(PROCESS_PALETTE)


class SimulationLog(models.Model):
    """Audit log of operating system events and memory allocations."""
    EVENT_TYPES = [
        ('INFO', 'Información'),
        ('PROCESS_CREATED', 'Proceso Creado'),
        ('PROCESS_ADMITTED', 'Asignado a Memoria'),
        ('PROCESS_QUEUED', 'En Cola de Espera'),
        ('PROCESS_FINISHED', 'Proceso Finalizado'),
        ('PROCESS_TERMINATED', 'Proceso Terminado'),
        ('MEMORY_FREED', 'Memoria Liberada'),
    ]

    tick = models.IntegerField(default=0)
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES, default='INFO')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"[T+{self.tick}s] [{self.event_type}] {self.message}"
