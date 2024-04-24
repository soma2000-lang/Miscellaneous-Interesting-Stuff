package io.conduktor.demos.kafka;

import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.time.Duration;
import java.util.Arrays;
import java.util.Properties;
public class ConsumerDemo {

    private static final Logger log = LoggerFactory.getLogger(ConsumerDemo.class.getSimpleName());
    public static void main(String[] args) {
        log.info("I am a Kafka Consumer!");
        String groupId = "my-java-application";
        String topic = "demo_java";
          // create Producer Properties
          Properties properties = new Properties();

           properties.setProperty("bootstrap.servers", "127.0.0.1:9092");
           properties.setProperty("bootstrap.servers", "cluster.playground.cdkt.io:9092");
           properties.setProperty("security.protocol", "SASL_SSL");
           properties.setProperty("sasl.jaas.config", "org.apache.kafka.common.security.plain.PlainLoginModule required username=\"your-username\" password=\"your-password\";");
           properties.setProperty("sasl.mechanism", "PLAIN");
           KafkaConsumer<String, String> consumer = new KafkaConsumer<>(properties);
           consumer.subscribe(Arrays.asList(topic));

           while (true) {

            log.info("Polling");

            ConsumerRecords<String, String> records =
                    consumer.poll(Duration.ofMillis(1000));

            for (ConsumerRecord<String, String> record: records) {
                log.info("Key: " + record.key() + ", Value: " + record.value());
                log.info("Partition: " + record.partition() + ", Offset: " + record.offset());
            }


        }


    }
}
