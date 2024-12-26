
import org.apache.kafka.common.serialization.StringSerializer;
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.clients.producer.KafkaProducer;

import java.util.Properties;

public class KafkaProducer2 {


    public static void main(String[] args) {
        String kafkaServer="localhost:9092";
        Properties properties=new Properties();
        properties.setProperty(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG,kafkaServer);
        properties.setProperty(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        properties.setProperty(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG,StringSerializer.class.getName());
        KafkaProducer<String,String> kafkaProducer=new KafkaProducer<String, String>(properties);
        ProducerRecord<String,String> record=new ProducerRecord<>("first_topic","message 1");
        kafkaProducer.send(record);
        kafkaProducer.flush();
        kafkaProducer.close();

    }
}
