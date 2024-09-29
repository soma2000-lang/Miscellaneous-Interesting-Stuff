import pika

def callback(ch, method, properties, body):
  print(" [X] Received %r" %body)


crdn = pika.PlainCredentials('user1', 'welcome123')

connection = pika.BlockingConnection(pika.ConnectionParameters('uvm3', credentials=crdn))

chnnel = connection.channel()

chnnel.queue_declare(queue='hello')

channel.basic_consume(callback, queue='hello', no_ack=true)

chnnel.start_consuming()


'''
root@ubuntu:/home/ubuntu#
root@ubuntu:/home/ubuntu# rabbitmqctl  add_user  user1 welcome123
Adding user "user1" ...
root@ubuntu:/home/ubuntu# rabbitmqctl set_permissions -p / user1  '.*' '.*' '.*'
Setting permissions for user "user1" in vhost "/" ...
root@ubuntu:/home/ubuntu# rabbitmqctl  set_user_tags   user1 administrator
Setting tags for user "user1" to [administrator] ...
root@ubuntu:/home/ubuntu#
'''