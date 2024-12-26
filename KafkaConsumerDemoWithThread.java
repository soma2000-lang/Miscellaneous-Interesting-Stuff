import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.errors.WakeupException;
import org.apache.kafka.common.protocol.types.Field;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import sun.dc.pr.PRError;

import java.time.Duration;
import java.util.Arrays;
import java.util.Properties;
import java.util.concurrent.CountDownLatch;


public class KafkaConsumerDemoWithThread {


    public static void main(String[] args) {

        new KafkaConsumerDemoWithThread().run();

    }

    private KafkaConsumerDemoWithThread(){


    }

    private void run(){

        Logger logger=LoggerFactory.getLogger(KafkaConsumerDemoWithThread.class.getName());

        String bootStrapServer="localhost:9092";
        String groupId="my-sixth-application";
        String topic="first_topic";

        CountDownLatch countDownLatch=new CountDownLatch(1);

        Runnable consumerThread=new ConsumerThread(countDownLatch,bootStrapServer,groupId,topic);

        Thread thread=new Thread(consumerThread);
        thread.start();

        // Add a shut down hook

        Runtime.getRuntime().addShutdownHook(new Thread( ()->{
            logger.info("Caught Shutdown hook");

            ((ConsumerThread)consumerThread).shutdown();

            try{
                countDownLatch.await();
            }catch (InterruptedException ex){
                ex.printStackTrace();
            }
            logger.info("Application has existed");

        }));
        try{
            countDownLatch.await();
        }catch (InterruptedException ex){
            ex.printStackTrace();
            logger.error("Application got Interrupted",ex);
        }finally {
            logger.info("Application is Closing");
        }

    }


    public class ConsumerThread implements Runnable {

        private CountDownLatch countDownLatch;
        private KafkaConsumer<String,String> kafkaConsumer;
        private Logger logger= LoggerFactory.getLogger(ConsumerThread.class.getName());

        public ConsumerThread(CountDownLatch countDownLatch,String bootStrapServer,String groupId,String topic){

            this.countDownLatch=countDownLatch;
            Properties properties=new Properties();

            properties.setProperty(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,bootStrapServer);
            properties.setProperty(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
            properties.setProperty(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG,StringDeserializer.class.getName());
            properties.setProperty(ConsumerConfig.GROUP_ID_CONFIG,groupId);
            properties.setProperty(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG,"earliest");
            this.kafkaConsumer=new KafkaConsumer<String, String>(properties);
            kafkaConsumer.subscribe(Arrays.asList(topic));

        }

        @Override
        public void run() {

            try{

                while (true){

                    ConsumerRecords<String,String> consumerRecords=kafkaConsumer.poll(Duration.ofMillis(100));

                    for(ConsumerRecord<String,String> record:consumerRecords){

                        logger.info("Key : "+record.key()+ " Value : "+record.value());
                        logger.info("Partition : "+record.partition()+" topic : "+record.topic()+" Offset : "+record.offset());
                    }
                }
            }catch (WakeupException we){

                logger.info("Received ShutDown Signal");
            }finally {
                kafkaConsumer.close();
                countDownLatch.countDown();
            }

        }

        public void shutdown(){

            kafkaConsumer.wakeup();
        }

    }
}
