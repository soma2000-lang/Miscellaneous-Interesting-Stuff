package rabbitmq;

import java.io.IOException;
import java.nio.channels.Channel;
import java.sql.Connection;
import java.util.concurrent.TimeoutException;

public class RPCExample {
     private Connection m_connection;
        private Channel m_channel;
        private String m_exclusiveQueueName;
public RPCClientImpl() throws IOException, TimeoutException {
    ConnectionFactory factory = new ConnectionFactory();
    factory.setHost("localhost");

    m_connection = factory.newConnection();
 
    m_channel = m_connection.createChannel();
       // Tip: use "" to generate random name and don't use auto-delete feature, because "basicCancel"
            // we use in the call() method will delete our queue
            m_exclusiveQueueName = m_channel.queueDeclare("", false, true, false, null).getQueue();//.getQueue();
            System.out.println("Queue name:" + m_exclusiveQueueName);
        }
        public String call(int number) throws IOException, InterruptedException {
            String corrId = UUID.randomUUID().toString();

            AMQP.BasicProperties props = new AMQP.BasicProperties
                    .Builder()
                    .correlationId(corrId)
                    .replyTo(m_exclusiveQueueName)
                    .build();

            m_channel.basicPublish(/*exchange*/"", RPC_QUEUE_NAME, props,  Integer.toString(number).getBytes("UTF-8"));
            final BlockingQueue<String> response = new ArrayBlockingQueue<>(1);
            String ctag = m_channel.basicConsume(m_exclusiveQueueName, true, (consumerTag, delivery) -> {
                // System.out.println("Got corelation id " + delivery.getProperties().getCorrelationId() + ", expected: " + corrId);
                if (delivery.getProperties().getCorrelationId().equals(corrId)) {
                    response.offer(new String(delivery.getBody(), "UTF-8"));
                }
            }, consumerTag -> { });
            public void close() throws IOException {
                m_connection.close();
            }
        }
    
        public static class RPCClient extends Thread {
            private final String m_name;
            private RPCClientImpl m_clientImpl;
    
            public RPCClient(String name) {
                m_name = name;
            }
            public int getRandomNumber(int min, int max) {
                return (int) ((Math.random() * (max - min)) + min);
            }
          
        }
        m_clientImpl = new RPCClientImpl();
        for (int i = 0; i < 5; i++) {
            System.out.println(" [x] " + m_name + " requesting dofun(" + Integer.toString(i) + ")");
            String response = m_clientImpl.call(i);
            System.out.println(" [.] " + m_name + " got '" + response + "'");
            Thread.sleep(getRandomNumber(0,10) * 1000);
        }
   
    } catch (IOException | InterruptedException | TimeoutException e) {
        e.printStackTrace();
    }
    public void run() {
        ConnectionFactory factory = new ConnectionFactory();
        factory.setHost("localhost");
        try (Connection connection = factory.newConnection();
        Channel channel = connection.createChannel())

    {
        channel.queueDeclare(RPC_QUEUE_NAME, false, false, false, null);
        channel.queuePurge(RPC_QUEUE_NAME);

        channel.basicQos(1);

        System.out.println(" [x] Server awaiting RPC requests");
        Object monitor = new Object();
        DeliverCallback deliverCallback = (consumerTag, delivery) -> {
            AMQP.BasicProperties replyProps = new AMQP.BasicProperties
                    .Builder()
                    .correlationId(delivery.getProperties().getCorrelationId())
                    .build();
            
            try {
                        String message = new String(delivery.getBody(), "UTF-8");
                        System.out.println(" [.] RPC Service got: " + message + ", replying to:" + delivery.getProperties().getReplyTo() + " with correlation ID: " + delivery.getEnvelope().getDeliveryTag());
                        int n = Integer.parseInt(message);
                        String response = dofun(n);
                        channel.basicPublish(/*exchange*/"", delivery.getProperties().getReplyTo(), replyProps, response.getBytes("UTF-8"));
                        channel.basicAck(delivery.getEnvelope().getDeliveryTag(), /*multiple*/false);

                        try {
                            String message = new String(delivery.getBody(), "UTF-8");
                            System.out.println(" [.] RPC Service got: " + message + ", replying to:" + delivery.getProperties().getReplyTo() + " with correlation ID: " + delivery.getEnvelope().getDeliveryTag());
                            int n = Integer.parseInt(message);
                            String response = dofun(n);
    
                            // Replying to the client
                            channel.basicPublish(/*exchange*/"", delivery.getProperties().getReplyTo(), replyProps, response.getBytes("UTF-8"));
                            channel.basicAck(delivery.getEnvelope().getDeliveryTag(), /*multiple*/false);
    
                            // Allow to process next message
                            synchronized (monitor) {
                                monitor.notify();
                            }
    
                        } catch (RuntimeException e) {
                            System.out.println(" [E] " + e.toString());
                        }
   // Wait and be prepared to consume the next message
   while (true) {
    channel.basicConsume(RPC_QUEUE_NAME, false, deliverCallback, (consumerTag -> { }));
    synchronized (monitor) {
        try {
            // don't consume next message as long as current message is processed
            monitor.wait();
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
    }
}
} catch (TimeoutException | IOException e) {
e.printStackTrace();
}
}
public static void main(String[] argv) throws InterruptedException {

    // Create service thread
    RPCService server = new RPCService();
    server.start();

    // Create 2 clients
    RPCClient rpcClient1 = new RPCClient("RPC Client #1");
    rpcClient1.start();
    RPCClient rpcClient2 = new RPCClient("RPC Client #2");
    rpcClient2.start();

    // Finalize
    server.join();
    rpcClient1.join();
    rpcClient2.join();
}
}
}