# master-slave-architecture
 
<img src="https://github.com/harsh6768/master-slave-architecture/blob/main/Screenshots/master_slave.png"/>


### Master-Slave Architecture 

Read full information about master-slave (super-replication) architecture in Database.

https://dev.mysql.com/doc/refman/8.0/en/replication.html#:~:text=Replication%20enables%20data%20from%20one,receive%20updates%20from%20a%20source.


### You can also checkout Digital Ocean documentation for step by step process.

https://www.digitalocean.com/community/tutorials/how-to-set-up-replication-in-mysql


#### On macOS, you can install MySQL easily using Homebrew.

https://flaviocopes.com/mysql-how-to-install/


#### Install MYSQL IN ec2

https://github.com/harsh6768/deploy-in-ec2

### Open mysql in terminal : 

use command : 

       mysql -u root -p
       
 
### After installing mysql in MASTER AND SLAVE instance we will start with Master configuration.


### 1. Master configuration changes : 

1. open mysqld.cnf using vi or nano editor to edit.
 
      vi /etc/mysql/mysql.conf.d/mysqld.cnf
      
   A. #bind-address  = 127.0.0.1
      
      Uncomment bind-address and Replace 127.0.0.1 with the master or source  server’s PRIVATE IP address. 
      
      after modification : 
      
       bind-address = master_private_ip
      
      
   B.  #server_id 
      Uncomment server_id and server_id can be any integer but it shoule be unique to all your database serverIds .
      
        server_id =1
        
   C.  # log_bin = /var/log/mysql/mysql-bin.log      Uncomment log bin in file
      
         log_bin = /var/log/mysql/mysql-bin.log
         
   D. # binlog_do_db = include_database_name        Uncomment binlog_do_db  in file
   
         binlog_do_db = db_name     // db_name should which one do you wanna replicate
         
         if there are more than one db then just copy and paste the above line 
         
         binlog_do_db = db_name1
         binlog_do_db = db_name2
         
         
   E. Alternatively, you can specify which databases MySQL should not replicate by adding a binlog_ignore_db directive for each one:
   
        binlog_ignore_db   = ignore_db_name
        
  now save the file and exit.
  
  
##### restart mysql after modification of /etc/mysql/mysql.conf.d/mysqld.cnf file

    
       sudo systemctl restart mysql
     
       or 
     
       sudo service mysql restart
     
       make your restart your mysql after modification else you can face any issues
    

#### mysql service start,status,restart and stop command 

     sudo service mysql start
     
     sudo service mysql stop
     
     sudo service mysql restart
     
     sudo service mysql status
     
     
 ### 2 Creating a Replication User : 
 
 
 Each replica in a MySQL replication environment connects to the source database with a username and password. Replicas can connect using any MySQL user    
 profile that exists on the source database and has the appropriate privileges, but this tutorial will outline how to create a dedicated user for this purpose.
     
     
  1. Start by opening up the MySQL shell:
     
          sudo mysql
          
          or
          
          mysql -u root -p  //if you have already created user for your database.
          
     
 2. Create new replica or slave user : 
     
          CREATE USER 'replica_user'@'replica_server_ip' IDENTIFIED WITH mysql_native_password BY 'password';
          
      
 3. After creating the new user, grant them the appropriate privileges. At minimum, a MySQL replication user must have the REPLICATION SLAVE permissions:

     
          GRANT REPLICATION SLAVE ON *.* TO 'replica_user'@'replica_server_ip';
          
          
 4.  it’s good practice to run the FLUSH PRIVILEGES command. This will free up any memory that the server cached as a result of the preceding CREATE USER and
     GRANT statements:
         
          FLUSH PRIVILEGES;


### 3. Retrieving Binary Log Coordinates from the Source
     
       

    1. From the prompt, run the following command which will close all the open tables in every database on your source instance and lock them:

           FLUSH TABLES WITH READ LOCK;
   
    2.  Check status of the master database 
    
    
           SHOW MASTER STATUS;

          
        you see the status of the master database , you need to copy file name , position 
        
        
        1. file name will be similar to : mysql-bin.000001
        2. position will be the number :  899


  
  
 
 
