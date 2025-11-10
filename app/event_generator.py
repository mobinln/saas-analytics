import json
import random
import time
from datetime import datetime, timedelta
from kafka import KafkaProducer
from faker import Faker
import uuid

fake = Faker()

# Simulate 10 different tenants (companies using your SaaS)
TENANTS = [
    {"tenant_id": f"tenant_{i}", "name": f"Company {chr(65+i)}", "plan": random.choice(["free", "pro", "enterprise"])}
    for i in range(10)
]

# Simulate users within each tenant
USERS = {}
for tenant in TENANTS:
    USERS[tenant["tenant_id"]] = [
        {
            "user_id": str(uuid.uuid4()),
            "email": fake.email(),
            "name": fake.name(),
            "role": random.choice(["admin", "member", "viewer"])
        }
        for _ in range(random.randint(5, 50))
    ]

# Event types your SaaS might track
EVENT_TYPES = [
    "page_view", "feature_used", "report_generated", 
    "user_invited", "file_uploaded", "api_call",
    "dashboard_viewed", "export_created"
]

def generate_event():
    """Generate a realistic SaaS usage event"""
    tenant = random.choice(TENANTS)
    user = random.choice(USERS[tenant["tenant_id"]])
    
    event = {
        "event_id": str(uuid.uuid4()),
        "tenant_id": tenant["tenant_id"],
        "user_id": user["user_id"],
        "event_type": random.choice(EVENT_TYPES),
        "timestamp": datetime.utcnow().isoformat(),
        "properties": {
            "session_id": str(uuid.uuid4()),
            "page_url": fake.url(),
            "duration_seconds": random.randint(1, 300),
            "device": random.choice(["desktop", "mobile", "tablet"]),
            "browser": random.choice(["chrome", "firefox", "safari", "edge"]),
            "feature_name": random.choice(["analytics", "reporting", "collaboration", "automation"]),
            "status": random.choice(["success", "success", "success", "error"])  # 75% success rate
        },
        "tenant_metadata": {
            "plan": tenant["plan"],
            "tenant_name": tenant["name"]
        }
    }
    
    return event

def produce_events():
    """Send events to Kafka"""
    producer = KafkaProducer(
        bootstrap_servers=['localhost:19092'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    print("Starting event generation...")
    
    try:
        while True:
            # Generate variable load (simulate peak hours)
            num_events = random.randint(10, 50)
            
            for _ in range(num_events):
                event = generate_event()
                producer.send('saas_events', value=event)
            
            producer.flush()
            print(f"Sent {num_events} events at {datetime.utcnow()}")
            
            # Random sleep between batches
            time.sleep(random.uniform(1, 5))
            
    except KeyboardInterrupt:
        print("\nStopping event generation...")
        producer.close()

if __name__ == "__main__":
    # First, create the tenant reference data
    print("Tenants:", json.dumps(TENANTS, indent=2))
    
    # Save tenant and user data to files for later use
    with open('tenants.json', 'w') as f:
        json.dump(TENANTS, f, indent=2)
    
    with open('users.json', 'w') as f:
        json.dump(USERS, f, indent=2)
    
    # Start producing events
    produce_events()