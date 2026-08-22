/**
 * Memory and Process Management Simulator - Frontend Engine
 */

let simulationInterval = null;
let currentSimData = null;

// Initialize on DOM loaded
document.addEventListener('DOMContentLoaded', () => {
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    setupEventListeners();

    if (typeof INITIAL_SIM_DATA !== 'undefined' && INITIAL_SIM_DATA) {
        renderSimulation(INITIAL_SIM_DATA);
    } else {
        fetchStatus();
    }
});

function setupEventListeners() {
    // RAM range slider input
    const ramSlider = document.getElementById('input-process-ram');
    const ramLabel = document.getElementById('label-ram-val');
    if (ramSlider && ramLabel) {
        ramSlider.addEventListener('input', (e) => {
            ramLabel.textContent = `${e.target.value} MB`;
        });
    }

    // RAM preset buttons
    document.querySelectorAll('.btn-ram-preset').forEach(btn => {
        btn.addEventListener('click', () => {
            const val = btn.getAttribute('data-val');
            if (ramSlider && ramLabel) {
                ramSlider.value = val;
                ramLabel.textContent = `${val} MB`;
            }
        });
    });

    // Form Create Single Process
    const formCreate = document.getElementById('form-create-process');
    if (formCreate) {
        formCreate.addEventListener('submit', handleCreateProcess);
    }

    // Button Generate Batch
    const btnBatch = document.getElementById('btn-generate-batch');
    if (btnBatch) {
        btnBatch.addEventListener('click', handleGenerateBatch);
    }

    // Simulation Controls: Toggle Play/Pause
    const btnToggle = document.getElementById('btn-toggle-sim');
    if (btnToggle) {
        btnToggle.addEventListener('click', handleToggleSimulation);
    }

    // Simulation Controls: Single Step Tick (+1s)
    const btnStep = document.getElementById('btn-tick-step');
    if (btnStep) {
        btnStep.addEventListener('click', handleTickStep);
    }

    // Simulation Controls: Reset
    const btnReset = document.getElementById('btn-reset-sim');
    if (btnReset) {
        btnReset.addEventListener('click', handleResetSimulation);
    }

    // Speed Selector
    const selectSpeed = document.getElementById('select-speed');
    if (selectSpeed) {
        selectSpeed.addEventListener('change', (e) => {
            updateSimulationParams({ speed_ms: parseInt(e.target.value) });
        });
    }

    // Algorithm Selector
    const selectAlgo = document.getElementById('select-algorithm');
    if (selectAlgo) {
        selectAlgo.addEventListener('change', (e) => {
            updateSimulationParams({ algorithm: e.target.value });
        });
    }
}

// Fetch Full Status
async function fetchStatus() {
    try {
        const res = await fetch('/api/status/');
        if (res.ok) {
            const data = await res.json();
            renderSimulation(data);
        }
    } catch (err) {
        console.error("Error fetching status:", err);
    }
}

// Single Process Creation Handler
async function handleCreateProcess(e) {
    e.preventDefault();
    const nameInput = document.getElementById('input-process-name');
    const pidInput = document.getElementById('input-process-pid');
    const ramInput = document.getElementById('input-process-ram');
    const durInput = document.getElementById('input-process-duration');

    const payload = {
        name: nameInput.value.trim() || null,
        pid: pidInput.value.trim() ? parseInt(pidInput.value.trim()) : null,
        required_memory: parseInt(ramInput.value) || 128,
        duration: parseInt(durInput.value) || 10
    };

    try {
        const res = await fetch('/api/process/create/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status) {
            renderSimulation(data.status);
            // Reset name & pid input for next process
            nameInput.value = '';
            pidInput.value = '';
        }
    } catch (err) {
        console.error("Error creating process:", err);
    }
}

// Batch Generation Handler
async function handleGenerateBatch() {
    const countSelect = document.getElementById('batch-count');
    const profileSelect = document.getElementById('batch-profile');

    const payload = {
        count: parseInt(countSelect.value) || 5,
        profile: profileSelect.value || 'mixed'
    };

    try {
        const res = await fetch('/api/process/batch/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status) {
            renderSimulation(data.status);
        }
    } catch (err) {
        console.error("Error generating batch:", err);
    }
}

// Toggle Play/Pause
async function handleToggleSimulation() {
    const isRunning = currentSimData ? !currentSimData.state.is_running : true;
    updateSimulationParams({ is_running: isRunning });
}

// Update simulation params (running state, speed, algorithm)
async function updateSimulationParams(params) {
    try {
        const res = await fetch('/api/simulation/toggle/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
        });
        const data = await res.json();
        if (data.status) {
            renderSimulation(data.status);
        }
    } catch (err) {
        console.error("Error updating simulation:", err);
    }
}

// Single Tick Step (+1s)
async function handleTickStep() {
    try {
        const res = await fetch('/api/simulation/tick/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await res.json();
        if (data.status) {
            renderSimulation(data.status);
        }
    } catch (err) {
        console.error("Error executing tick:", err);
    }
}

// Reset Simulation
async function handleResetSimulation() {
    if (!confirm("¿Deseas reiniciar la simulación y limpiar todos los procesos y memoria?")) {
        return;
    }
    try {
        const res = await fetch('/api/simulation/reset/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await res.json();
        if (data.status) {
            renderSimulation(data.status);
        }
    } catch (err) {
        console.error("Error resetting simulation:", err);
    }
}

// Terminate / Kill Process
async function terminateProcess(pid) {
    try {
        const res = await fetch(`/api/process/${pid}/terminate/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await res.json();
        if (data.status) {
            renderSimulation(data.status);
        }
    } catch (err) {
        console.error("Error terminating process:", err);
    }
}

// Auto-Tick Loop Management
function manageSimulationTimer(state) {
    if (simulationInterval) {
        clearInterval(simulationInterval);
        simulationInterval = null;
    }

    if (state.is_running) {
        simulationInterval = setInterval(() => {
            handleTickStep();
        }, state.speed_ms || 1000);
    }
}

// Main Render Function
function renderSimulation(data) {
    currentSimData = data;
    const { state, memory, counts, running_processes, waiting_processes, completed_processes, logs } = data;

    // 1. Header & Controls
    const clockDisplay = document.getElementById('clock-tick-display');
    if (clockDisplay) clockDisplay.textContent = `T = ${state.current_tick}s`;

    const algoBadge = document.getElementById('header-algorithm-badge');
    if (algoBadge) algoBadge.textContent = state.algorithm.replace('_', ' ');

    const btnToggle = document.getElementById('btn-toggle-sim');
    const btnToggleText = document.getElementById('btn-toggle-text');
    const iconPlay = document.getElementById('icon-play');

    if (btnToggle && btnToggleText) {
        if (state.is_running) {
            btnToggleText.textContent = 'Pausar';
            btnToggle.className = 'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold bg-amber-600 hover:bg-amber-500 text-white shadow transition-all ring-2 ring-amber-400/40';
            if (iconPlay) iconPlay.setAttribute('data-lucide', 'pause');
        } else {
            btnToggleText.textContent = 'Iniciar';
            btnToggle.className = 'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow transition-all';
            if (iconPlay) iconPlay.setAttribute('data-lucide', 'play');
        }
    }

    // Selectors sync
    const selectSpeed = document.getElementById('select-speed');
    if (selectSpeed && selectSpeed.value != state.speed_ms) {
        selectSpeed.value = state.speed_ms;
    }

    const selectAlgo = document.getElementById('select-algorithm');
    if (selectAlgo && selectAlgo.value != state.algorithm) {
        selectAlgo.value = state.algorithm;
    }

    // 2. Metrics Cards
    document.getElementById('metric-ram-used').textContent = memory.used_mb;
    document.getElementById('metric-ram-free').textContent = `${memory.free_mb} MB`;
    document.getElementById('metric-ram-percent-badge').textContent = `${memory.used_percent}%`;
    document.getElementById('metric-ram-bar').style.width = `${memory.used_percent}%`;
    document.getElementById('metric-frag-count').textContent = `${memory.fragmentation_count} ${memory.fragmentation_count === 1 ? 'bloque' : 'bloques'}`;

    document.getElementById('metric-running-count').textContent = counts.running;
    document.getElementById('badge-running-subtotal').textContent = `${counts.running} activos`;

    document.getElementById('metric-waiting-count').textContent = counts.waiting;
    document.getElementById('badge-waiting-subtotal').textContent = `${counts.waiting} en cola`;

    document.getElementById('metric-completed-count').textContent = counts.completed + counts.terminated;
    document.getElementById('badge-completed-subtotal').textContent = `${counts.completed + counts.terminated} finalizados`;

    // 3. Render Dynamic RAM Memory Map
    renderMemoryMap(memory.blocks);

    // 4. Render Running Processes Table
    renderRunningTable(running_processes);

    // 5. Render Waiting Queue Table
    renderWaitingTable(waiting_processes, memory);

    // 6. Render Completed History Table
    renderCompletedTable(completed_processes);

    // 7. Render Logs Terminal
    renderLogs(logs);

    // 8. Re-init icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    // 9. Sync interval
    manageSimulationTimer(state);
}

// Render Memory Blocks
function renderMemoryMap(blocks) {
    const container = document.getElementById('memory-map-container');
    if (!container) return;

    if (!blocks || blocks.length === 0) {
        container.innerHTML = `<div class="w-full h-full flex items-center justify-center text-xs text-slate-500">Memoria 1024 MB Libre</div>`;
        return;
    }

    container.innerHTML = '';

    blocks.forEach(block => {
        const widthPercent = ((block.size / 1024) * 100).toFixed(2);
        const blockDiv = document.createElement('div');
        blockDiv.style.width = `${widthPercent}%`;
        blockDiv.className = 'h-full flex flex-col justify-center items-center relative overflow-hidden rounded text-[11px] font-mono transition-all';

        if (block.is_free) {
            blockDiv.classList.add('free-memory-block', 'text-slate-400');
            blockDiv.title = `Espacio Libre: ${block.size} MB [${block.start} MB - ${block.end} MB]`;
            blockDiv.innerHTML = `
                <div class="truncate px-1 text-center font-sans text-[10px] text-slate-400">
                    ${block.size >= 48 ? `Libre: ${block.size}M` : `${block.size}M`}
                </div>
            `;
            blockDiv.addEventListener('click', () => {
                inspectBlock(block);
            });
        } else {
            blockDiv.classList.add('memory-block-item', 'text-white', 'shadow-sm');
            blockDiv.style.backgroundColor = block.process_color || '#0284c7';
            blockDiv.title = `PID ${block.process_pid} (${block.process_name}) | ${block.size} MB [${block.start} MB - ${block.end} MB] | Restante: ${block.remaining_time}s`;
            
            blockDiv.innerHTML = `
                <div class="w-full px-1 flex flex-col items-center justify-center pointer-events-none drop-shadow">
                    <span class="font-bold truncate text-[10px] sm:text-xs">PID ${block.process_pid}</span>
                    <span class="text-[9px] opacity-90 truncate">${block.size} MB</span>
                    ${block.remaining_time !== null ? `<span class="text-[8px] opacity-80">${block.remaining_time}s</span>` : ''}
                </div>
            `;
            blockDiv.addEventListener('click', () => {
                inspectBlock(block);
            });
        }

        container.appendChild(blockDiv);
    });
}

function inspectBlock(block) {
    const textEl = document.getElementById('inspector-block-text');
    const actionsEl = document.getElementById('inspector-actions');

    if (block.is_free) {
        textEl.innerHTML = `<span class="text-emerald-400 font-bold">Bloque Libre:</span> Tamaño ${block.size} MB (Rango de direcciones: [${block.start} MB — ${block.end} MB])`;
        actionsEl.className = 'hidden';
    } else {
        textEl.innerHTML = `
            <span class="font-bold" style="color: ${block.process_color}">PID ${block.process_pid} (${block.process_name}):</span>
            ${block.size} MB asignados [${block.start} MB — ${block.end} MB] • Tiempo restante: <strong class="text-amber-300">${block.remaining_time}s</strong> / ${block.duration}s (${block.progress}%)
        `;
        actionsEl.className = 'flex items-center gap-2';
        actionsEl.innerHTML = `
            <button onclick="terminateProcess(${block.process_pid})" class="px-2 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white font-sans text-xs font-semibold shadow transition-all">
                Terminar PID ${block.process_pid}
            </button>
        `;
    }
}

// Render Running Table
function renderRunningTable(processes) {
    const tbody = document.getElementById('table-running-body');
    if (!tbody) return;

    if (!processes || processes.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="py-6 text-center text-slate-500 italic">
                    No hay procesos en ejecución en este momento. Crea o genera procesos para comenzar.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = processes.map(proc => {
        return `
            <tr class="hover:bg-slate-800/40 transition-colors">
                <td class="py-2.5 px-4">
                    <div class="flex items-center gap-2">
                        <span class="h-2.5 w-2.5 rounded-full" style="background-color: ${proc.color}"></span>
                        <span class="font-mono font-bold text-white">#${proc.pid}</span>
                        <span class="font-medium text-slate-300 truncate max-w-[120px]">${proc.name}</span>
                    </div>
                </td>
                <td class="py-2.5 px-3 font-mono font-semibold text-cyan-300">
                    ${proc.required_memory} MB
                </td>
                <td class="py-2.5 px-3 font-mono text-slate-400 text-[11px]">
                    [${proc.memory_start_address} — ${proc.memory_end_address} MB]
                </td>
                <td class="py-2.5 px-4">
                    <div class="space-y-1">
                        <div class="flex justify-between text-[11px]">
                            <span class="font-mono text-amber-300 font-semibold">${proc.remaining_time}s restantes</span>
                            <span class="text-slate-400 font-mono">${proc.progress}%</span>
                        </div>
                        <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                            <div class="h-full rounded-full transition-all duration-300" style="width: ${proc.progress}%; background-color: ${proc.color}"></div>
                        </div>
                    </div>
                </td>
                <td class="py-2.5 px-3 text-right">
                    <button onclick="terminateProcess(${proc.pid})" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-rose-950 hover:text-rose-300 hover:border-rose-800 border border-slate-700 text-slate-300 text-[11px] font-medium transition-all" title="Forzar terminación y liberar memoria">
                        Terminar
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// Render Waiting Queue Table
function renderWaitingTable(processes, memory) {
    const tbody = document.getElementById('table-waiting-body');
    if (!tbody) return;

    if (!processes || processes.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="py-6 text-center text-slate-500 italic">
                    La cola de espera está vacía.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = processes.map((proc, index) => {
        const canFitSoon = memory.max_contiguous_free_mb >= proc.required_memory;
        const reasonText = canFitSoon 
            ? `<span class="text-emerald-400 font-medium">Listo para entrar en el próximo ciclo</span>`
            : `<span class="text-amber-400">Requiere ${proc.required_memory} MB (Espacio libre máx: ${memory.max_contiguous_free_mb} MB)</span>`;

        return `
            <tr class="hover:bg-slate-800/40 transition-colors">
                <td class="py-2.5 px-4 font-mono">
                    <span class="text-amber-400 font-bold">#${index + 1}</span>
                    <span class="text-slate-400 ml-1.5">(PID ${proc.pid})</span>
                </td>
                <td class="py-2.5 px-3 font-medium text-slate-300 truncate max-w-[120px]">
                    ${proc.name}
                </td>
                <td class="py-2.5 px-3 font-mono font-semibold text-amber-300">
                    ${proc.required_memory} MB
                </td>
                <td class="py-2.5 px-3 font-mono text-slate-400">
                    ${proc.duration}s
                </td>
                <td class="py-2.5 px-4 text-[11px]">
                    ${reasonText}
                </td>
                <td class="py-2.5 px-3 text-right">
                    <button onclick="terminateProcess(${proc.pid})" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 text-[11px] transition-all">
                        Cancelar
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// Render Completed Table
function renderCompletedTable(processes) {
    const tbody = document.getElementById('table-completed-body');
    if (!tbody) return;

    if (!processes || processes.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="py-4 text-center text-slate-500 italic">
                    Aún no hay procesos en el historial.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = processes.map(proc => {
        const isTerminated = proc.status === 'TERMINATED';
        const badge = isTerminated 
            ? `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-300 border border-rose-800">Terminado</span>`
            : `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">Completado</span>`;

        return `
            <tr class="hover:bg-slate-800/40 transition-colors">
                <td class="py-2 px-4 font-mono font-bold text-slate-300">PID ${proc.pid}</td>
                <td class="py-2 px-3 text-slate-300">${proc.name}</td>
                <td class="py-2 px-3 font-mono text-emerald-400 font-semibold">${proc.required_memory} MB</td>
                <td class="py-2 px-3 font-mono text-slate-400">${proc.duration}s</td>
                <td class="py-2 px-3 font-mono text-cyan-400">T+${proc.finished_at_tick ?? '-'}s</td>
                <td class="py-2 px-3">${badge}</td>
            </tr>
        `;
    }).join('');
}

// Render Logs Terminal
function renderLogs(logs) {
    const container = document.getElementById('system-logs-container');
    if (!container) return;

    if (!logs || logs.length === 0) {
        container.innerHTML = `<div class="text-slate-500 italic">[T+0s] Esperando eventos del sistema...</div>`;
        return;
    }

    container.innerHTML = logs.map(log => {
        let cssClass = 'log-item-INFO';
        if (log.event_type.includes('ADMITTED')) cssClass = 'log-item-ADMITTED';
        else if (log.event_type.includes('QUEUED')) cssClass = 'log-item-QUEUED';
        else if (log.event_type.includes('FINISHED')) cssClass = 'log-item-FINISHED';
        else if (log.event_type.includes('TERMINATED')) cssClass = 'log-item-TERMINATED';
        else if (log.event_type.includes('CREATED')) cssClass = 'log-item-CREATED';

        return `
            <div class="py-1 ${cssClass}">
                <span class="text-slate-500">[T+${log.tick}s]</span>
                <span class="text-[10px] font-semibold uppercase opacity-75 mr-1">[${log.event_type_display || log.event_type}]</span>
                <span>${log.message}</span>
            </div>
        `;
    }).join('');
}
