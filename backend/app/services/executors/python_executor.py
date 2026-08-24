import os
from app.models.execution import ExecutionLanguage
from app.services.executors.base import BaseExecutor


class PythonExecutor(BaseExecutor):
    """
    Executor for Python 3 code.
    """

    def __init__(self, image_name: str = "runtime-debugger-python", timeout: float = 5.0):
        super().__init__(image_name=image_name, timeout=timeout)

    def get_language(self) -> ExecutionLanguage:
        return ExecutionLanguage.PYTHON

    def prepare_files(self, temp_dir: str, code: str) -> str:
        filename = "script.py"
        file_path = os.path.join(temp_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        runner = os.path.join(temp_dir, "_trace_runner.py")
        with open(runner, "w", encoding="utf-8") as f:
            f.write('''import json, sys, time, traceback
START=time.perf_counter(); events=[]; MAX=2000; truncated=False
def safe(value):
    try:
        if isinstance(value, (str,int,float,bool)) or value is None: result=value
        elif isinstance(value, (list,tuple)): result=[safe(x) for x in value[:20]]
        elif isinstance(value, dict): result={str(k)[:80]:safe(v) for k,v in list(value.items())[:20]}
        else: result="<%s>" % type(value).__name__
        text=repr(result)
        return result if len(text)<=500 else text[:497]+"..."
    except Exception: return "<unserializable>"
def stack(frame):
    output=[]; current=frame; index=0
    while current and index<25:
        if current.f_code.co_filename.endswith("script.py"):
            output.append({"frame_id":index,"function":current.f_code.co_name,"file":"script.py","line":current.f_lineno,"variables":{k:safe(v) for k,v in current.f_locals.items() if not k.startswith("__")}}); index+=1
        current=current.f_back
    return output
def trace(frame, event, arg):
    global truncated
    if not frame.f_code.co_filename.endswith("script.py"): return trace
    if len(events)>=MAX: truncated=True; return trace
    item={"event_id":len(events)+2,"event_type":{"call":"function_call","line":"line_execution","return":"function_return","exception":"exception"}.get(event,event),"language":"python","file":"script.py","line":frame.f_lineno,"function":frame.f_code.co_name,"timestamp":round(time.perf_counter()-START,6),"stack":stack(frame)}
    if event in ("line","return"): item["variables"]={k:safe(v) for k,v in frame.f_locals.items() if not k.startswith("__")}
    if event=="exception":
        typ,val,_=arg; item["exception"]={"type":typ.__name__,"message":str(val)[:500]}
    events.append(item); return trace
events.append({"event_id":1,"event_type":"program_start","language":"python","file":"script.py","timestamp":0.0})
try:
    source=open("script.py",encoding="utf-8").read(); compiled=compile(source,"script.py","exec")
    sys.settrace(trace); exec(compiled,{"__name__":"__main__","__file__":"script.py"})
except BaseException as exc:
    if not any(e.get("event_type")=="exception" for e in events): events.append({"event_id":len(events)+2,"event_type":"exception","language":"python","file":"script.py","line":getattr(exc,"lineno",None),"timestamp":round(time.perf_counter()-START,6),"exception":{"type":type(exc).__name__,"message":str(exc)[:500]}})
    raise
finally:
    sys.settrace(None); events.append({"event_id":len(events)+2,"event_type":"program_end","language":"python","file":"script.py","timestamp":round(time.perf_counter()-START,6)})
    with open(".runtime_trace.json","w",encoding="utf-8") as out: json.dump({"events":events,"truncated":truncated},out)
''')
        return filename

    def build_execution_command(self, filename: str) -> str:
        return "python3 _trace_runner.py"
