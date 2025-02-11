// cdc-streamer.js
const { Client } = require('pg');
const amqp = require('amqplib');

class PostgresCDCStreamer {
    constructor(config) {
        this.pgConfig = config.postgres;
        this.rmqConfig = config.rabbitmq;
        this.slotName = 'cdc_slot';
        this.publicationName = 'cdc_publication';
    }

    async initialize() {
        try {
            // Setup PostgreSQL connection
            this.pgClient = new Client(this.pgConfig);
            await this.pgClient.connect();

            // Setup RabbitMQ connection
            this.rmqConnection = await amqp.connect(this.rmqConfig.url);
            this.rmqChannel = await this.rmqConnection.createChannel();
            await this.rmqChannel.assertExchange(this.rmqConfig.exchange, 'topic', { durable: true });

            // Setup logical replication
            await this.setupReplication();
            
            console.log('CDC Streamer initialized successfully');
        } catch (error) {
            console.error('Initialization failed:', error);
            throw error;
        }
    }

    async setupReplication() {
        // Enable logical replication for the database
        await this.pgClient.query(`
            ALTER SYSTEM SET wal_level = logical;
        `);

        // Create publication if it doesn't exist
        await this.pgClient.query(`
            CREATE PUBLICATION IF NOT EXISTS ${this.publicationName} 
            FOR ALL TABLES;
        `);

        // Create replication slot if it doesn't exist
        await this.pgClient.query(`
            SELECT pg_create_logical_replication_slot(
                '${this.slotName}',
                'pgoutput'
            ) WHERE NOT EXISTS (
                SELECT 1 FROM pg_replication_slots 
                WHERE slot_name = '${this.slotName}'
            );
        `);
    }

    async startStreaming() {
        try {
            const replicationClient = new Client({
                ...this.pgConfig,
                replication: 'database'
            });

            await replicationClient.connect();

            // Start logical replication
            const stream = await replicationClient.query(`
                START_REPLICATION SLOT ${this.slotName} 
                LOGICAL 0/0 
                (proto_version '1', 
                publication_names '${this.publicationName}')
            `);

            stream.on('data', async (msg) => {
                const change = this.parseWalMessage(msg);
                if (change) {
                    await this.publishToRabbitMQ(change);
                }
            });

            stream.on('error', (error) => {
                console.error('Streaming error:', error);
                this.handleStreamError(error);
            });

            console.log('Started streaming database changes');
        } catch (error) {
            console.error('Failed to start streaming:', error);
            throw error;
        }
    }

    parseWalMessage(msg) {
        try {
            // Parse the WAL message based on pgoutput format
            const change = {
                operation: msg.command,
                schema: msg.schema,
                table: msg.table,
                data: msg.data
            };

            return change;
        } catch (error) {
            console.error('Error parsing WAL message:', error);
            return null;
        }
    }

    async publishToRabbitMQ(change) {
        try {
            const routingKey = `${change.schema}.${change.table}.${change.operation}`;
            await this.rmqChannel.publish(
                this.rmqConfig.exchange,
                routingKey,
                Buffer.from(JSON.stringify(change)),
                { persistent: true }
            );

            console.log(`Published change: ${routingKey}`);
        } catch (error) {
            console.error('Failed to publish to RabbitMQ:', error);
            throw error;
        }
    }

    async handleStreamError(error) {
        console.error('Stream error occurred:', error);
        // Implement retry logic or alerting mechanism
        await this.cleanup();
        process.exit(1);
    }

    async cleanup() {
        try {
            if (this.pgClient) {
                await this.pgClient.end();
            }
            if (this.rmqChannel) {
                await this.rmqChannel.close();
            }
            if (this.rmqConnection) {
                await this.rmqConnection.close();
            }
            console.log('Cleanup completed');
        } catch (error) {
            console.error('Cleanup failed:', error);
        }
    }
}

// Usage example
const config = {
    postgres: {
        host: 'localhost',
        port: 5432,
        database: 'your_database',
        user: 'your_user',
        password: 'your_password'
    },
    rabbitmq: {
        url: 'amqp://localhost',
        exchange: 'cdc_exchange'
    }
};

async function main() {
    const streamer = new PostgresCDCStreamer(config);
    
    try {
        await streamer.initialize();
        await streamer.startStreaming();

        // Handle graceful shutdown
        process.on('SIGINT', async () => {
            console.log('Shutting down...');
            await streamer.cleanup();
            process.exit(0);
        });
    } catch (error) {
        console.error('Main process error:', error);
        await streamer.cleanup();
        process.exit(1);
    }
}

main();
