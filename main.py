#!/usr/bin/env python3
"""
Iris Smart Glasses - Main Orchestrator

Entry point that runs on the laptop. This is the "brain" that:
- Discovers and connects to Pi Zero W for display
- Connects to phone or laptop mic for audio
- Manages state machine and voice command processing
- Coordinates with IoT devices
"""

import argparse
import asyncio
import signal
import sys
import logging
import yaml
import time
from datetime import datetime
from typing import Dict, Any, Optional

from dotenv import load_dotenv

# Import core modules
from core.discovery import create_registry, DeviceRegistry
from core.parser import CommandParser, State, ParseResult
from core.display import Display
from core.audio import create_audio_source, AudioSource
from core.iot import IoTClient, DeviceOfflineError
from core.server import start_server, InterruptManager, Interrupt, InterruptType

# Import features
from features.weather import Weather
from features.todo import TodoList
from features.translation import Translator


logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    
    # Reduce noise from some modules
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Iris Smart Glasses')
    
    # Core modes
    parser.add_argument('--mock', action='store_true', 
                       help='Full mock mode (no hardware)')
    parser.add_argument('--debug-hardware', action='store_true',
                       help='Run hardware diagnostic mode')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    # Audio source options
    parser.add_argument('--audio-source', choices=['laptop', 'ipwebcam', 'mock'],
                       default=None,
                       help='Audio input source (default: from config or laptop)')
    parser.add_argument('--phone-ip', type=str, default=None,
                       help='Phone IP for ipwebcam audio source')
    
    # Display hardware options
    parser.add_argument('--display', choices=['none', 'terminal', 'nano', 'esp32', 'pi'],
                       default=None,
                       help='Display hardware (default: terminal in mock, pi in real mode)')
    parser.add_argument('--display-ip', type=str, default=None,
                       help='IP address for ESP32 display (required for --display esp32)')
    parser.add_argument('--serial-port', type=str, default=None,
                       help='Serial port for Nano display (default: auto-detect)')
    
    parser.add_argument('--test-mode', action='store_true',
                       help='Quick test mode for validation (exits after setup)')
    
    return parser.parse_args()


def load_config() -> Dict[str, Any]:
    """Load configuration from config.yaml and environment variables."""
    # Load environment variables
    load_dotenv()
    
    # Load YAML config
    config = {}
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning("config.yaml not found, using defaults")
    except yaml.YAMLError as e:
        logger.error(f"Error parsing config.yaml: {e}")
    
    return config


async def handle_interrupt(interrupt: Interrupt, display: Display, parser: CommandParser) -> None:
    """Handle motion and other interrupts."""
    if interrupt.type == InterruptType.MOTION:
        logger.info(f"Motion detected from {interrupt.source_ip}")
        
        # Only show motion interrupt if motion sensor is enabled
        # (In a real implementation, we'd check motion sensor state)
        display.show_motion_interrupt(duration=2.0)
        
    elif interrupt.type == InterruptType.DEVICE_OFFLINE:
        device_type = interrupt.data.get('type', 'unknown')
        logger.warning(f"Device {device_type} went offline")
        
    elif interrupt.type == InterruptType.DEVICE_ONLINE:
        device_type = interrupt.data.get('type', 'unknown')
        logger.info(f"Device {device_type} came online")


async def handle_state_change(new_state: State, display: Display, weather: Weather, 
                             todo: TodoList, iot: IoTClient, registry: DeviceRegistry, device_cursor: int = 0) -> None:
    """Handle state transitions from timeout."""
    if new_state == State.IDLE:
        # Show weather/time screen
        current_weather = weather.get_current()
        display.show_idle(current_weather)
        
    elif new_state == State.MAIN_MENU:
        display.show_main_menu()
        
    elif new_state == State.TODO_MENU:
        display.show_todo_menu()
        
    elif new_state == State.TODO_LIST:
        todos = todo.get_visible(window=3)
        display.show_todo_list(todos, cursor=todo.cursor_index)
        
    elif new_state == State.DEVICE_LIST:
        devices = registry.get_device_list_for_display()
        display.show_device_list(devices, cursor=device_cursor)


async def handle_command(result: ParseResult, display: Display, iot: IoTClient, 
                        todo: TodoList, translator: Translator, weather: Weather, 
                        registry: DeviceRegistry, parser: CommandParser, device_cursor: int) -> int:
    """Handle parsed voice commands."""
    
    if not result.action:
        return device_cursor
    
    try:
        # Scroll actions (work for both todo and device lists)
        if result.action == "scroll_up":
            if parser.current_state == State.TODO_LIST:
                todo.scroll_up()
                todos = todo.get_visible(window=3)
                display.show_todo_list(todos, cursor=todo.cursor_index)
            elif parser.current_state == State.DEVICE_LIST:
                devices = registry.get_device_list_for_display()
                if device_cursor > 0:
                    device_cursor -= 1
                display.show_device_list(devices, cursor=device_cursor)
                
        elif result.action == "scroll_down":
            if parser.current_state == State.TODO_LIST:
                todo.scroll_down()
                todos = todo.get_visible(window=3)
                display.show_todo_list(todos, cursor=todo.cursor_index)
            elif parser.current_state == State.DEVICE_LIST:
                devices = registry.get_device_list_for_display()
                if device_cursor < len(devices) - 1:
                    device_cursor += 1
                display.show_device_list(devices, cursor=device_cursor)
                
        elif result.action == "mark_done":
            todo.cross()
            if parser.current_state == State.TODO_LIST:
                todos = todo.get_visible(window=3)
                display.show_todo_list(todos, cursor=todo.cursor_index)
                
        elif result.action == "mark_undone":
            todo.uncross()
            if parser.current_state == State.TODO_LIST:
                todos = todo.get_visible(window=3)
                display.show_todo_list(todos, cursor=todo.cursor_index)
                
        elif result.action == "add_todo":
            todo_text = result.data.get("text", "")
            if todo_text:
                todo.add(todo_text)
                todos = todo.get_visible(window=3)
                display.show_todo_list(todos, cursor=todo.cursor_index)
                
        elif result.action == "capture_todo_text":
            captured_text = result.data.get("text", "")
            display.show_todo_add(captured_text)
        
        # Translation actions
        elif result.action == "translate":
            text = result.data.get("text", "")
            if text:
                translation_result = translator.translate_continuous(text)
                display.show_translation(
                    original=translation_result['original'],
                    translated=translation_result['translated']
                )
        
        # IoT device actions
        elif result.action in ["light_on", "light_off"]:
            command = "on" if result.action == "light_on" else "off"
            try:
                response = iot.send_command("light", command)
                status = response.get("status", "unknown").upper()
                display.show_connected_light(status)
            except DeviceOfflineError:
                display.show_connection_error("Light")
                
        elif result.action in ["fan_on", "fan_off", "fan_low", "fan_high"]:
            command_map = {
                "fan_on": "on",
                "fan_off": "off", 
                "fan_low": "low",
                "fan_high": "high"
            }
            command = command_map[result.action]
            
            try:
                response = iot.send_command("fan", command)
                status = response.get("status", "unknown").upper()
                speed = response.get("speed", "").upper()
                display.show_connected_fan(status, speed)
            except DeviceOfflineError:
                display.show_connection_error("Fan")
                
        elif result.action in ["motion_on", "motion_off"]:
            command = "on" if result.action == "motion_on" else "off"
            try:
                response = iot.send_command("motion", command)
                alerts_enabled = response.get("alerts") == "enabled"
                display.show_connected_motion(alerts_enabled)
            except DeviceOfflineError:
                display.show_connection_error("Motion Sensor")
        
        elif result.action == "send_message":
            message = result.data.get("message", "")
            try:
                lines = [message[:21], "", "Message sent", ""]
                success = iot.send_to_glasses("glasses", lines)
                if success:
                    display.show_connected_glasses()
            except DeviceOfflineError:
                display.show_connection_error("Glasses 2")
        
        # Device list actions
        elif result.action == "connect_current":
            # Connect to currently highlighted device
            devices = registry.get_device_list_for_display()
            if devices:
                current_device = devices[0]  # Simplified - assume first is current
                device_type = current_device.get('type')
                if device_type:
                    new_state = parser.connect_to_device(device_type)
                    parser._transition_to(new_state)
                    await _show_connected_device_screen(device_type, display, iot)
        
        elif result.action == "connect_named":
            device_name = result.data.get("name", "")
            # Map device name to type
            name_mapping = parser.get_device_name_mapping()
            device_type = name_mapping.get(device_name.lower())
            
            if device_type and registry.is_device_online(device_type):
                new_state = parser.connect_to_device(device_type)
                parser._transition_to(new_state)
                await _show_connected_device_screen(device_type, display, iot)
        
        elif result.action == "connect_numbered":
            device_index = result.data.get("index", 0)
            devices = registry.get_device_list_for_display()
            if 0 <= device_index < len(devices):
                device = devices[device_index]
                device_type = device.get('type')
                if device_type and registry.is_device_online(device_type):
                    new_state = parser.connect_to_device(device_type)
                    parser._transition_to(new_state)
                    await _show_connected_device_screen(device_type, display, iot)
                
    except Exception as e:
        logger.error(f"Error handling command {result.action}: {e}")
        display.show_text(f"Error: {str(e)[:40]}")
    
    return device_cursor


async def _show_connected_device_screen(device_type: str, display: Display, iot: IoTClient) -> None:
    """Show the appropriate connected device screen."""
    try:
        if device_type == "light":
            status = iot.get_device_status("light")
            display.show_connected_light(status.get("status", "unknown").upper())
            
        elif device_type == "fan":
            status = iot.get_device_status("fan")
            display.show_connected_fan(
                status.get("status", "unknown").upper(),
                status.get("speed", "").upper()
            )
            
        elif device_type == "motion":
            status = iot.get_device_status("motion")
            alerts_enabled = status.get("alerts") == "enabled"
            display.show_connected_motion(alerts_enabled)
            
        elif device_type == "distance":
            distance = iot.get_distance_reading("distance")
            display.show_connected_distance(distance)
            
        elif device_type == "glasses":
            display.show_connected_glasses()
            
    except DeviceOfflineError:
        display.show_connection_error(f"{device_type.title()}")


async def main_loop(args, config: Dict[str, Any]) -> None:
    """Main application loop."""
    
    # Step 1: Setup audio source
    logger.info("[1/6] Setting up audio...")
    
    if args.mock:
        audio_source_type = "mock"
    elif args.audio_source:
        audio_source_type = args.audio_source
    else:
        audio_source_type = config.get('audio_source', 'laptop')
    
    phone_ip = None
    if audio_source_type == "ipwebcam":
        phone_ip = args.phone_ip or config.get('phone_ip')
        if not phone_ip:
            print("\nPhone IP not configured.")
            print("Open IP Webcam app on Android and find the IP address.")
            phone_ip = input("Enter phone IP: ").strip()
    
    audio = create_audio_source(audio_source_type, phone_ip)
    
    if not audio.is_available():
        logger.warning("Audio source not available, falling back to keyboard input")
        audio = create_audio_source("mock", None)
    
    logger.info(f"✅ Audio ready ({audio_source_type})")
    
    # Step 2: Determine display type (moved from Step 3 for conditional discovery)
    logger.info("[2/6] Determining display type...")
    display_type = args.display
    if display_type is None:
        display_type = "terminal" if args.mock else "pi"
    
    # Validate ESP32 display requirements early
    if display_type == "esp32" and not args.display_ip:
        logger.error("ESP32 display requires --display-ip parameter")
        sys.exit(1)
        
    logger.info(f"Display type: {display_type}")
    
    # Step 3: Conditional device discovery
    logger.info("[3/6] Discovering devices...")
    registry = create_registry(mock=args.mock, config=config)
    
    if args.test_mode:
        logger.info("✅ Test mode: Basic setup successful")
        return
    
    # Only wait for Pi if we're actually using Pi display
    if display_type == "pi" and not args.mock:
        logger.info("Waiting for Pi display...")
        try:
            registry.wait_for_device("pi", timeout=60)
            logger.info("✅ Pi found")
        except TimeoutError:
            logger.error("❌ Pi not found! Cannot continue without Pi display.")
            logger.error("   Use --display terminal to test without Pi hardware")
            sys.exit(1)
    elif not args.mock:
        logger.info("Skipping Pi discovery (not using Pi display)")
    
    # Discover other IoT devices (non-blocking)
    if not args.mock:
        for device in ["light", "fan", "motion", "distance", "glasses"]:
            if registry.is_device_online(device):
                logger.info(f"✅ {device} found")
            else:
                logger.info(f"⚪ {device} not found (will retry in background)")
    else:
        logger.info("✅ Mock devices loaded")
    
    # Step 4: Initialize components
    logger.info("[4/6] Initializing components...")
    parser = CommandParser(registry, timeout_seconds=config.get('timeout_seconds', 10))
    
    # Initialize display with pre-determined type
    display_kwargs = {}
    if display_type == "esp32":
        display_kwargs['display_ip'] = args.display_ip
    elif display_type == "nano":
        display_kwargs['serial_port'] = args.serial_port
        
    display = Display(
        display_type=display_type,
        registry=registry,
        mock=args.mock,
        **display_kwargs
    )
    iot = IoTClient(registry=registry, mock=args.mock)
    weather = Weather(mock=args.mock)
    todo = TodoList()
    translator = Translator(mock=args.mock)
    interrupt_manager = InterruptManager()
    
    # Device list cursor management
    device_cursor = 0
    
    logger.info("✅ Components ready")
    logger.info(f"Display: {display_type}")
    
    # Step 5: Start background services
    logger.info("[5/6] Starting services...")
    server_port = config.get('server', {}).get('port', 5000)
    start_server(interrupt_manager, port=server_port)
    
    if not args.mock:
        registry.start_background_scan()
    
    logger.info("✅ Services running")
    
    # Step 6: Distance sensor polling (if available)
    distance_task = None
    if registry.is_device_online("distance"):
        async def poll_distance():
            while True:
                if parser.get_current_state() == State.CONNECTED_DISTANCE:
                    try:
                        distance = iot.get_distance_reading("distance")
                        display.show_connected_distance(distance)
                    except:
                        pass
                await asyncio.sleep(0.2)  # 200ms polling
        
        distance_task = asyncio.create_task(poll_distance())
        logger.info("✅ Distance polling started")
    
    # Step 7: Start main loop
    logger.info("[6/6] Starting main loop...")
    logger.info("=" * 50)
    logger.info("System ready!")
    logger.info("")
    logger.info("  Say 'Hey Iris' to begin")
    if audio_source_type == "mock":
        logger.info("  (Type commands and press Enter)")
    elif audio_source_type == "laptop":
        logger.info("  (Speak into laptop microphone)")
    else:
        logger.info("  (Speak into phone)")
    logger.info("")
    logger.info("=" * 50 + "\n")
    
    # Show initial IDLE screen
    current_weather = weather.get_current()
    display.show_idle(current_weather)
    
    # Main loop
    try:
        while True:
            # Check for interrupts (motion alerts, etc)
            interrupt = interrupt_manager.poll()
            if interrupt:
                await handle_interrupt(interrupt, display, parser)
                continue
            
            # Check timeout
            timeout_result = parser.check_timeout()
            if timeout_result:
                await handle_state_change(timeout_result, display, weather, todo, iot, registry, device_cursor)
            
            # Listen for voice (or keyboard in mock)
            transcript = audio.listen(timeout=0.5)
            if transcript:
                logger.info(f"Heard: '{transcript}'")
                result = parser.parse(transcript)
                
                # Handle state transitions from commands
                if result.new_state:
                    await handle_state_change(result.new_state, display, weather, todo, iot, registry, device_cursor)
                # Handle other command actions
                elif result.action:
                    device_cursor = await handle_command(result, display, iot, todo, translator, weather, registry, parser, device_cursor)
                # Show feedback for unrecognized commands
                else:
                    logger.warning(f"Command not recognized: '{transcript}'")
                    display.show_text("Command not\nrecognized", center=True)
                    # Brief pause to show the message
                    await asyncio.sleep(1.5)
                    # Restore the current state display
                    current_state = parser.get_current_state()
                    await handle_state_change(current_state, display, weather, todo, iot, registry, device_cursor)
            
            # Small sleep to prevent CPU spinning
            await asyncio.sleep(0.01)
            
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    finally:
        # Cleanup
        if distance_task:
            distance_task.cancel()
        display.clear()
        display.disconnect()
        registry.stop()
        interrupt_manager.stop()


async def run_hardware_debug():
    """Run hardware diagnostic mode."""
    from core.debug import run_hardware_debug
    await run_hardware_debug()


async def main():
    """Main entry point."""
    args = parse_args()
    
    setup_logging(verbose=args.verbose)
    
    logger.info("=" * 50)
    logger.info("       IRIS SMART GLASSES")
    logger.info("=" * 50)
    logger.info(f"Mode: {'MOCK' if args.mock else 'REAL'}")
    
    # Handle debug mode separately  
    if args.debug_hardware:
        await run_hardware_debug()
        return
    
    # Load configuration
    config = load_config()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await main_loop(args, config)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())