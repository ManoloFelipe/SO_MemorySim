class MemoryBlock:
    """Represents a continuous segment of RAM."""
    def __init__(self, start: int, end: int, is_free: bool = True, process=None):
        self.start = start # in MB
        self.end = end     # in MB
        self.size = end - start
        self.is_free = is_free
        self.process = process

    def to_dict(self):
        return {
            'start': self.start,
            'end': self.end,
            'size': self.size,
            'is_free': self.is_free,
            'process_pid': self.process.pid if self.process else None,
            'process_name': self.process.name if self.process else None,
            'process_color': self.process.color if self.process else '#E2E8F0',
            'remaining_time': self.process.remaining_time if self.process else None,
            'duration': self.process.duration if self.process else None,
            'progress': self.process.progress_percentage if self.process else 0,
        }


class MemoryManager:
    """
    Handles dynamic RAM allocation and deallocation within a 1024 MB space.
    Supports First-Fit, Best-Fit, and Worst-Fit algorithms with contiguous partition tracking.
    """
    def __init__(self, total_memory: int = 1024):
        self.total_memory = total_memory

    def get_memory_layout(self, running_processes):
        """
        Returns a list of all memory blocks (both used and free) spanning from 0 to total_memory MB.
        """
        # Sort running processes by their start address
        sorted_procs = sorted(
            [p for p in running_processes if p.memory_start_address is not None],
            key=lambda p: p.memory_start_address
        )

        blocks = []
        current_addr = 0

        for proc in sorted_procs:
            if proc.memory_start_address > current_addr:
                # There is a free gap before this process
                blocks.append(MemoryBlock(
                    start=current_addr,
                    end=proc.memory_start_address,
                    is_free=True
                ))

            # Used block by this process
            blocks.append(MemoryBlock(
                start=proc.memory_start_address,
                end=proc.memory_end_address,
                is_free=False,
                process=proc
            ))
            current_addr = proc.memory_end_address

        # Check for free space at the end
        if current_addr < self.total_memory:
            blocks.append(MemoryBlock(
                start=current_addr,
                end=self.total_memory,
                is_free=True
            ))

        return blocks

    def get_free_blocks(self, running_processes):
        """Returns only the free blocks in memory."""
        layout = self.get_memory_layout(running_processes)
        return [b for b in layout if b.is_free]

    def allocate(self, required_mb: int, running_processes, algorithm: str = 'FIRST_FIT'):
        """
        Attempts to allocate `required_mb` contiguous memory for a process.
        Returns (allocated: bool, start_addr: int | None, end_addr: int | None)
        """
        if required_mb <= 0 or required_mb > self.total_memory:
            return False, None, None

        free_blocks = self.get_free_blocks(running_processes)
        suitable_blocks = [b for b in free_blocks if b.size >= required_mb]

        if not suitable_blocks:
            return False, None, None

        selected_block = None

        if algorithm == 'BEST_FIT':
            # Smallest block that fits
            selected_block = min(suitable_blocks, key=lambda b: b.size)
        elif algorithm == 'WORST_FIT':
            # Largest block
            selected_block = max(suitable_blocks, key=lambda b: b.size)
        else:
            # Default: FIRST_FIT (first block with enough capacity)
            selected_block = suitable_blocks[0]

        start_addr = selected_block.start
        end_addr = start_addr + required_mb

        return True, start_addr, end_addr

    def get_memory_stats(self, running_processes):
        """Calculates memory usage metrics."""
        layout = self.get_memory_layout(running_processes)
        used_mb = sum(b.size for b in layout if not b.is_free)
        free_mb = self.total_memory - used_mb
        used_percent = round((used_mb / self.total_memory) * 100, 1) if self.total_memory > 0 else 0
        free_percent = round(100 - used_percent, 1)

        free_blocks = [b for b in layout if b.is_free]
        max_contiguous_free = max([b.size for b in free_blocks], default=0)
        fragmentation_count = len(free_blocks)

        return {
            'total_mb': self.total_memory,
            'used_mb': used_mb,
            'free_mb': free_mb,
            'used_percent': used_percent,
            'free_percent': free_percent,
            'max_contiguous_free_mb': max_contiguous_free,
            'fragmentation_count': fragmentation_count,
            'blocks': [b.to_dict() for b in layout]
        }
