import os
import sys
import time
import json
import asyncio
import tempfile
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.models.execution import ExecutionLanguage
from app.services.executors.python_executor import PythonExecutor
from app.services.executors.java_executor import JavaExecutor

router = APIRouter()

python_executor = PythonExecutor()
java_executor = JavaExecutor()


@router.websocket("/ws/execute")
async def websocket_execution_endpoint(websocket: WebSocket):
    await websocket.accept()
    temp_dir = None
    process = None

    try:
        # Step 1: Wait for initial execution config payload
        init_data_raw = await websocket.receive_text()
        init_data = json.loads(init_data_raw)

        language_str = init_data.get("language", "").lower()
        code = init_data.get("code", "")

        if not code.strip():
            await websocket.send_json({
                "type": "stderr",
                "data": "Error: Submitted code is empty.\r\n"
            })
            await websocket.send_json({
                "type": "exit",
                "exit_code": 1,
                "execution_time": 0.0
            })
            await websocket.close()
            return

        temp_dir = tempfile.mkdtemp(prefix="ws_debugger_sandbox_")

        # Step 2: Prepare files and compilation command depending on language
        if language_str == "python":
            filename = python_executor.prepare_files(temp_dir, code)
            # -u flag disables Python stdout buffering so print prompts (e.g. input("Name: ")) stream live
            if sys.platform == "win32":
                run_cmd = f'"{sys.executable}" -u {filename}'
            else:
                run_cmd = f'python3 -u {filename}'

        elif language_str == "java":
            filename = java_executor.prepare_files(temp_dir, code)
            path_without_ext = os.path.splitext(filename)[0]
            fqcn = path_without_ext.replace("/", ".").replace("\\", ".")

            # Compile step first
            compile_cmd = f"javac -d . {filename}"
            compile_proc = await asyncio.create_subprocess_shell(
                compile_cmd,
                cwd=temp_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            comp_stdout, comp_stderr = await compile_proc.communicate()

            if compile_proc.returncode != 0:
                stderr_text = comp_stderr.decode('utf-8', errors='replace').replace('\n', '\r\n')
                await websocket.send_json({
                    "type": "stderr",
                    "data": f"Compilation Error:\r\n{stderr_text}"
                })
                await websocket.send_json({
                    "type": "exit",
                    "exit_code": compile_proc.returncode,
                    "execution_time": 0.0
                })
                await websocket.close()
                return

            run_cmd = f"java {fqcn}"
        else:
            await websocket.send_json({
                "type": "stderr",
                "data": f"Error: Unsupported language '{language_str}'.\r\n"
            })
            await websocket.send_json({
                "type": "exit",
                "exit_code": 1,
                "execution_time": 0.0
            })
            await websocket.close()
            return

        # Step 3: Spawn interactive sub-process with unbuffered pipes
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["JAVA_TOOL_OPTIONS"] = "-Dfile.encoding=UTF-8"

        start_time = time.time()
        process = await asyncio.create_subprocess_shell(
            run_cmd,
            cwd=temp_dir,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )

        # Notify frontend client that process started
        await websocket.send_json({
            "type": "status",
            "data": "running"
        })

        # Step 4: Define stream reader tasks
        async def stream_reader(stream, stream_type: str):
            try:
                while True:
                    chunk = await stream.read(512)
                    if not chunk:
                        break
                    text = chunk.decode('utf-8', errors='replace').replace('\n', '\r\n')
                    await websocket.send_json({
                        "type": stream_type,
                        "data": text
                    })
            except Exception:
                pass

        async def input_listener():
            try:
                while True:
                    msg_text = await websocket.receive_text()
                    msg = json.loads(msg_text)
                    if msg.get("type") == "input":
                        input_data = msg.get("data", "")
                        if process and process.stdin:
                            process.stdin.write(input_data.encode('utf-8'))
                            await process.stdin.drain()
            except (WebSocketDisconnect, asyncio.CancelledError):
                pass
            except Exception:
                pass

        reader_tasks = asyncio.gather(
            stream_reader(process.stdout, "stdout"),
            stream_reader(process.stderr, "stderr")
        )
        listener_task = asyncio.create_task(input_listener())

        # Wait for process exit or timeout (30 seconds for live interactive session)
        try:
            await asyncio.wait_for(process.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except Exception:
                pass
            await websocket.send_json({
                "type": "stderr",
                "data": "\r\n[Execution timed out after 30 seconds]\r\n"
            })

        await reader_tasks
        listener_task.cancel()

        elapsed_time = round(time.time() - start_time, 3)

        await websocket.send_json({
            "type": "exit",
            "exit_code": process.returncode if process.returncode is not None else 1,
            "execution_time": elapsed_time
        })

    except WebSocketDisconnect:
        if process:
            try:
                process.kill()
            except Exception:
                pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "stderr",
                "data": f"Server Error: {str(e)}\r\n"
            })
        except Exception:
            pass
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
        try:
            await websocket.close()
        except Exception:
            pass
