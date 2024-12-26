import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.util.Arrays;
import java.util.Properties;

public class KafkaConsumerPlay {

    public static void main(String[] args) {

        Logger logger= LoggerFactory.getLogger(KafkaConsumerPlay.class.getName());

        String bootStrapServer="127.0.0.1:9092";

        String groupId="my-application";

        String topic="first_topic";

        Properties properties=new Properties();

        properties.setProperty(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,bootStrapServer);
        properties.setProperty(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        properties.setProperty(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG,StringDeserializer.class.getName());
        properties.setProperty(ConsumerConfig.GROUP_ID_CONFIG,groupId);
        properties.setProperty(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG,"earliest");

        KafkaConsumer<String,String> kafkaConsumer=new KafkaConsumer<String, String>(properties);

        kafkaConsumer.subscribe(Arrays.asList(topic));

        while(true){

            ConsumerRecords<String,String> records=kafkaConsumer.poll(Duration.ofMillis(100));

            for(ConsumerRecord<String,String> record:records){

                logger.info("Key : "+record.key()+ " Value : "+record.value());
                logger.info("Partiton: "+record.partition()+ "  ,Offset : "+record.offset());
            }
        }

    }
}
