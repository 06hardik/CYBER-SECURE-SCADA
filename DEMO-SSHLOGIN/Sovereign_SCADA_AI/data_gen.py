import pandas as pd
import random

def generate_logs(num_entries=10000):
    users = ['admin_01', 'operator_02', 'guest_user', 'maintenance_bot']
    actions = ['read_temp', 'check_valve', 'status_ping', 'write_firmware', 'emergency_stop']
    targets = ['turbine_A', 'boiler_04', 'plc_controller', 'grid_switch']
    
    data = []
    for _ in range(num_entries):
        is_anomaly = 0
        user = random.choice(users)
        action = random.choice(actions)
        target = random.choice(targets)
        hour = random.randint(0, 23)

        # Logic for Anomalies (The "Hack" patterns)
        if (user == 'guest_user' and 'write' in action) or \
           (hour < 5 and action == 'write_firmware') or \
           (user == 'maintenance_bot' and target == 'grid_switch'):
            is_anomaly = 1
        
        log = f"[{hour:02d}:00] USER: {user} ACTION: {action} TARGET: {target}"
        data.append([log, is_anomaly])
    
    df = pd.DataFrame(data, columns=['log', 'label'])
    df.to_csv('scada_logs.csv', index=False)
    print(f"Generated {num_entries} logs in scada_logs.csv")

if __name__ == "__main__":
    generate_logs()