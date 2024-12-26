import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.serialization.StringSerializer;

import java.util.Properties;

public class KafkaProducerCallbackPlay {

    public static void main(String[] args) {

        String kafkaServer="localhost:9092";
        Properties properties=new Properties();
        properties.setProperty(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG,kafkaServer);
        properties.setProperty(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        properties.setProperty(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG,StringSerializer.class.getName());
        KafkaProducer<String,String> kafkaProducer=new KafkaProducer<String, String>(properties);

        for(int i=0;i<10;i++){

            ProducerRecord<String,String> record=new ProducerRecord<>("first_topic","message 1"+Integer.toString(i));
            kafkaProducer.send(record, new Callback() {
                @Override
                public void onCompletion(RecordMetadata recordMetadata, Exception e) {
                    if(e==null){

                        System.out.println("Recived New Meta Data \n"+
                        "Topic"+recordMetadata.topic()+"\n"+
                        "Partition"+recordMetadata.partition()+"\n"+
                        "OffSet"+recordMetadata.offset()+"\n"+
                         "TimeStamp"+record.timestamp()
                        );

                    }else{
                        System.out.println("Error While Producing Messages ");
                    }
                }
            });

        }



    }
}
