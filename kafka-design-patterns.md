# Kafka Design Patterns

## 1. Producer-Consumer Pattern

The most basic Kafka pattern where producers publish messages to topics, and consumers read from these topics.

```python
from kafka import KafkaProducer, KafkaConsumer
import json

# Producer
producer = KafkaProducer(bootstrap_servers=['localhost:9092'],
                         value_serializer=lambda v: json.dumps(v).encode('utf-8'))

producer.send('my-topic', {'key': 'value'})

# Consumer
consumer = KafkaConsumer('my-topic',
                         bootstrap_servers=['localhost:9092'],
                         value_deserializer=lambda m: json.loads(m.decode('utf-8')))

for message in consumer:
    print(message.value)
```

## 2. Publish-Subscribe Pattern

Multiple consumers can subscribe to the same topic, each receiving all messages.

```python
# Consumer Group 1
consumer1 = KafkaConsumer('my-topic', group_id='group1',
                          bootstrap_servers=['localhost:9092'])

# Consumer Group 2
consumer2 = KafkaConsumer('my-topic', group_id='group2',
                          bootstrap_servers=['localhost:9092'])
```

## 3. Stream Processing Pattern

Using Kafka Streams API for real-time stream processing.

```java
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.kstream.KStream;

StreamsBuilder builder = new StreamsBuilder();
KStream<String, String> source = builder.stream("input-topic");

KStream<String, String> transformed = source.mapValues(value -> value.toUpperCase());
transformed.to("output-topic");
```

## 4. Event Sourcing Pattern

Using Kafka as an event store to capture all changes to an application state as a sequence of events.

```python
def create_user(user_data):
    event = {
        'type': 'USER_CREATED',
        'data': user_data,
        'timestamp': datetime.now().isoformat()
    }
    producer.send('user-events', event)

def update_user(user_id, update_data):
    event = {
        'type': 'USER_UPDATED',
        'user_id': user_id,
        'data': update_data,
        'timestamp': datetime.now().isoformat()
    }
    producer.send('user-events', event)
```

## 5. CQRS (Command Query Responsibility Segregation) Pattern

Separate write (command) and read (query) operations using Kafka as the event store.

```python
# Command side
def execute_command(command):
    # Process command
    event = create_event_from_command(command)
    producer.send('domain-events', event)

# Query side
consumer = KafkaConsumer('domain-events', group_id='query-model-updater')
for message in consumer:
    event = message.value
    update_query_model(event)
```

## 6. Saga Pattern

Manage distributed transactions across multiple services using Kafka for coordination.

```python
def start_saga(order_data):
    saga_id = generate_unique_id()
    producer.send('order-saga', {
        'saga_id': saga_id,
        'step': 'CREATE_ORDER',
        'data': order_data
    })

def handle_saga_step(message):
    if message['step'] == 'CREATE_ORDER':
        create_order(message['data'])
        producer.send('order-saga', {
            'saga_id': message['saga_id'],
            'step': 'RESERVE_INVENTORY',
            'data': message['data']
        })
    elif message['step'] == 'RESERVE_INVENTORY':
        reserve_inventory(message['data'])
        producer.send('order-saga', {
            'saga_id': message['saga_id'],
            'step': 'PROCESS_PAYMENT',
            'data': message['data']
        })
    # ... handle other steps
```

## 7. Dead Letter Queue Pattern

Handle messages that can't be processed by sending them to a separate topic for later analysis or reprocessing.

```python
def process_message(message):
    try:
        # Process the message
        pass
    except Exception as e:
        producer.send('dead-letter-queue', {
            'original_message': message,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        })

consumer = KafkaConsumer('my-topic', group_id='my-group')
for message in consumer:
    process_message(message)
```

## 8. Outbox Pattern

Ensure reliable message production by first storing messages in a database "outbox" before sending to Kafka.

```python
def create_order(order_data):
    with transaction.atomic():
        order = Order.objects.create(**order_data)
        Outbox.objects.create(
            aggregate_type='Order',
            aggregate_id=order.id,
            event_type='OrderCreated',
            payload=json.dumps(order_data)
        )

def process_outbox():
    for outbox_message in Outbox.objects.all():
        producer.send('orders', outbox_message.payload)
        outbox_message.delete()
```

## 9. Partitioning Strategy Pattern

Implement custom partitioning to ensure related messages are processed by the same consumer.

```python
from kafka.partitioner import Partitioner

class CustomPartitioner(Partitioner):
    def partition(self, key, all_partitions, available_partitions):
        if key is None:
            return self.random(available_partitions)
        return hash(key) % len(available_partitions)

producer = KafkaProducer(partitioner=CustomPartitioner())
```

## 10. Exactly-Once Processing Pattern

Achieve exactly-once semantics using Kafka transactions.

```python
producer = KafkaProducer(bootstrap_servers=['localhost:9092'],
                         transactional_id='my-transactional-id')

producer.init_transactions()
try:
    producer.begin_transaction()
    producer.send('topic1', b'message1')
    producer.send('topic2', b'message2')
    producer.commit_transaction()
except Exception:
    producer.abort_transaction()
```

