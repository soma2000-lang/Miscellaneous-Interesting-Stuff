# Kafka Implementation for Payment Webhooks

## 1. System Architecture

```
[Payment Provider] --> [Webhook Receiver] --> [Kafka] --> [Payment Processor] --> [Database]
```

## 2. Kafka Setup

### 2.1 Kafka Topic Configuration

```java
import org.apache.kafka.clients.admin.AdminClient;
import org.apache.kafka.clients.admin.NewTopic;

public class KafkaTopicConfig {
    public static void createTopic(String topicName, int partitions, short replicationFactor) {
        Properties props = new Properties();
        props.put("bootstrap.servers", "localhost:9092");
        
        AdminClient admin = AdminClient.create(props);
        
        NewTopic newTopic = new NewTopic(topicName, partitions, replicationFactor);
        admin.createTopics(Collections.singleton(newTopic));
        
        admin.close();
    }
}

// Usage
KafkaTopicConfig.createTopic("payment-webhooks", 3, (short) 3);
```

## 3. Webhook Receiver

### 3.1 Webhook Endpoint

```java
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class WebhookController {

    private final KafkaTemplate<String, String> kafkaTemplate;

    public WebhookController(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    @PostMapping("/payment-webhook")
    public ResponseEntity<String> receiveWebhook(@RequestBody String payload) {
        try {
            // Validate the webhook payload
            if (!isValidWebhook(payload)) {
                return ResponseEntity.badRequest().body("Invalid webhook payload");
            }

            // Extract payment ID from payload
            String paymentId = extractPaymentId(payload);

            // Send to Kafka
            kafkaTemplate.send("payment-webhooks", paymentId, payload);

            return ResponseEntity.ok("Webhook received and processed");
        } catch (Exception e) {
            logger.error("Error processing webhook", e);
            return ResponseEntity.status(500).body("Error processing webhook");
        }
    }

    private boolean isValidWebhook(String payload) {
        // Implement webhook validation logic
        // e.g., signature verification, payload structure check
        return true;
    }

    private String extractPaymentId(String payload) {
        // Extract payment ID from payload
        // This is a simplified example
        JSONObject jsonPayload = new JSONObject(payload);
        return jsonPayload.getString("payment_id");
    }
}
```

## 4. Kafka Producer Configuration

```java
import org.apache.kafka.clients.producer.ProducerConfig;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;

@Configuration
public class KafkaProducerConfig {

    @Bean
    public ProducerFactory<String, String> producerFactory() {
        Map<String, Object> configProps = new HashMap<>();
        configProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        configProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        configProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        // Enable idempotence to prevent duplicate messages
        configProps.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, "true");
        return new DefaultKafkaProducerFactory<>(configProps);
    }

    @Bean
    public KafkaTemplate<String, String> kafkaTemplate() {
        return new KafkaTemplate<>(producerFactory());
    }
}
```

## 5. Kafka Consumer (Payment Processor)

```java
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;

@Service
public class PaymentProcessor {

    private final PaymentRepository paymentRepository;

    public PaymentProcessor(PaymentRepository paymentRepository) {
        this.paymentRepository = paymentRepository;
    }

    @KafkaListener(topics = "payment-webhooks", groupId = "payment-processor-group")
    public void processPayment(String payload) {
        try {
            JSONObject jsonPayload = new JSONObject(payload);
            String paymentId = jsonPayload.getString("payment_id");
            String status = jsonPayload.getString("status");

            // Update payment status in database
            Payment payment = paymentRepository.findById(paymentId)
                .orElseThrow(() -> new PaymentNotFoundException(paymentId));
            payment.setStatus(status);
            paymentRepository.save(payment);

            // Additional business logic...

        } catch (Exception e) {
            logger.error("Error processing payment", e);
            // Implement retry logic or dead letter queue here
        }
    }
}
```

## 6. Kafka Consumer Configuration

```java
@Configuration
public class KafkaConsumerConfig {

    @Bean
    public ConsumerFactory<String, String> consumerFactory() {
        Map<String, Object> props = new HashMap<>();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ConsumerConfig.GROUP_ID_CONFIG, "payment-processor-group");
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        // Enable exactly-once semantics
        props.put(ConsumerConfig.ISOLATION_LEVEL_CONFIG, "read_committed");
        return new DefaultKafkaConsumerFactory<>(props);
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, String> kafkaListenerContainerFactory() {
        ConcurrentKafkaListenerContainerFactory<String, String> factory =
            new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(consumerFactory());
        return factory;
    }
}
```

## 7. Error Handling and Retries

```java
@Configuration
public class KafkaErrorHandlingConfig {

    @Bean
    public ConsumerAwareListenerErrorHandler listenerErrorHandler() {
        return (message, exception, consumer) -> {
            logger.error("Error processing message: " + message.getPayload(), exception);
            // Implement retry logic or send to dead letter queue
            return null;
        };
    }
}

// In PaymentProcessor class
@KafkaListener(topics = "payment-webhooks", groupId = "payment-processor-group", 
               errorHandler = "listenerErrorHandler")
public void processPayment(String payload) {
    // ... existing processing logic
}
```

## 8. Monitoring and Logging

```java
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

@Component
public class KafkaMetrics {

    private final MeterRegistry meterRegistry;

    public KafkaMetrics(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
    }

    public void recordProcessedPayment() {
        meterRegistry.counter("processed.payments").increment();
    }

    public void recordProcessingTime(long milliseconds) {
        meterRegistry.timer("payment.processing.time").record(milliseconds, TimeUnit.MILLISECONDS);
    }
}

// Usage in PaymentProcessor
@Autowired
private KafkaMetrics kafkaMetrics;

@KafkaListener(topics = "payment-webhooks", groupId = "payment-processor-group")
public void processPayment(String payload) {
    long startTime = System.currentTimeMillis();
    try {
        // ... processing logic
        kafkaMetrics.recordProcessedPayment();
    } finally {
        long processingTime = System.currentTimeMillis() - startTime;
        kafkaMetrics.recordProcessingTime(processingTime);
    }
}
```

