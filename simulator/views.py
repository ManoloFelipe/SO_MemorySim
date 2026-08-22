import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .services import SimulationEngine


def index(request):
    """Render the main simulation dashboard page."""
    engine = SimulationEngine()
    initial_status = engine.get_full_status()
    return render(request, 'simulator/index.html', {
        'initial_data_json': json.dumps(initial_status)
    })


@require_http_methods(["GET"])
def api_status(request):
    """Returns the current simulation and memory status."""
    engine = SimulationEngine()
    return JsonResponse(engine.get_full_status())


@csrf_exempt
@require_http_methods(["POST"])
def api_create_process(request):
    """Endpoint to create a new single process."""
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        data = request.POST

    name = data.get('name')
    required_memory = data.get('required_memory', 128)
    duration = data.get('duration', 10)
    pid = data.get('pid')

    try:
        required_memory = int(required_memory)
        duration = int(duration)
        pid = int(pid) if pid else None
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetros numéricos inválidos'}, status=400)

    engine = SimulationEngine()
    proc = engine.create_process(
        name=name,
        required_memory=required_memory,
        duration=duration,
        pid=pid
    )

    return JsonResponse({
        'success': True,
        'message': f"Proceso {proc.pid} creado con éxito",
        'status': engine.get_full_status()
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_create_batch(request):
    """Endpoint to create multiple random processes."""
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        data = request.POST

    count = int(data.get('count', 5))
    profile = data.get('profile', 'mixed')

    engine = SimulationEngine()
    engine.generate_batch(count=count, profile=profile)

    return JsonResponse({
        'success': True,
        'message': f"Lote de {count} procesos generado",
        'status': engine.get_full_status()
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_tick(request):
    """Advances the simulation by 1 clock tick (1 second)."""
    engine = SimulationEngine()
    result = engine.tick()
    status = engine.get_full_status()
    return JsonResponse({
        'success': True,
        'tick_result': result,
        'status': status
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_toggle_simulation(request):
    """Starts, pauses, or updates simulation running parameters."""
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        data = request.POST

    is_running = data.get('is_running')
    speed_ms = data.get('speed_ms')
    algorithm = data.get('algorithm')

    engine = SimulationEngine()
    if is_running is not None:
        is_running = bool(is_running)
    else:
        is_running = not engine.state.is_running

    engine.set_running_state(
        is_running=is_running,
        speed_ms=speed_ms,
        algorithm=algorithm
    )

    return JsonResponse({
        'success': True,
        'is_running': engine.state.is_running,
        'speed_ms': engine.state.speed_ms,
        'algorithm': engine.state.algorithm,
        'status': engine.get_full_status()
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_terminate_process(request, pid):
    """Terminates a running or waiting process."""
    engine = SimulationEngine()
    success, msg = engine.terminate_process(pid=int(pid))
    if not success:
        return JsonResponse({'success': False, 'message': msg}, status=400)

    return JsonResponse({
        'success': True,
        'message': msg,
        'status': engine.get_full_status()
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_reset(request):
    """Resets the simulation, clearing processes and logs."""
    engine = SimulationEngine()
    engine.reset_simulation()
    return JsonResponse({
        'success': True,
        'message': "Simulador reiniciado",
        'status': engine.get_full_status()
    })
