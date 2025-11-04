# flight_sim_stub.py
import os, time, math, random

os.makedirs("logs", exist_ok=True)
ts = time.strftime("%Y%m%d_%H%M%S")
path = os.path.join("logs", f"telemetry_{ts}.csv")

header = "t,x,y,vx,vy,pitch,roll,engine_out\n"
with open(path, "w", encoding="utf-8") as f:
    f.write(header)

print("Escribiendo:", path, "(Ctrl+C para parar)")
t = 0.0
x, y = 0.0, 10.0
vx, vy = 20.0, 0.0
engine_out = 0
try:
    while True:
        t += 0.2
        x += vx * 0.2
        y += vy * 0.2 + math.sin(t*0.4)*0.2
        pitch = 0.03*math.sin(t*0.6) + random.uniform(-0.005, 0.005)
        roll  = 0.05*math.sin(t*0.3) + random.uniform(-0.01, 0.01)
        vy = (math.sin(t*0.5))*2.0

        line = f"{t:.2f},{x:.2f},{y:.2f},{vx:.2f},{vy:.2f},{pitch:.4f},{roll:.4f},{engine_out}\n"
        with open(path, "a", encoding="utf-8") as fa:
            fa.write(line)
        time.sleep(0.2)
except KeyboardInterrupt:
    print("\nfin.")
