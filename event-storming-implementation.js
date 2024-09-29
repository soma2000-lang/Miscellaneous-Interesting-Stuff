// Domain Events
class DomainEvent {
    constructor(aggregateId, eventData) {
        this.aggregateId = aggregateId;
        this.eventData = eventData;
        this.timestamp = new Date();
    }
}

class OrderPlaced extends DomainEvent {}
class PaymentReceived extends DomainEvent {}
class OrderShipped extends DomainEvent {}

// Commands
class Command {
    constructor(aggregateId, commandData) {
        this.aggregateId = aggregateId;
        this.commandData = commandData;
    }
}

class PlaceOrder extends Command {}
class ProcessPayment extends Command {}
class ShipOrder extends Command {}

// Aggregate
class Order {
    constructor(id) {
        this.id = id;
        this.status = 'created';
        this.items = [];
        this.totalAmount = 0;
    }

    applyEvent(event) {
        if (event instanceof OrderPlaced) {
            this.status = 'placed';
            this.items = event.eventData.items;
            this.totalAmount = event.eventData.totalAmount;
        } else if (event instanceof PaymentReceived) {
            this.status = 'paid';
        } else if (event instanceof OrderShipped) {
            this.status = 'shipped';
        }
    }
}

// Event Store
class EventStore {
    constructor() {
        this.events = [];
    }

    saveEvent(event) {
        this.events.push(event);
    }

    getEventsForAggregate(aggregateId) {
        return this.events.filter(event => event.aggregateId === aggregateId);
    }
}

// Command Handler
class CommandHandler {
    constructor(eventStore) {
        this.eventStore = eventStore;
    }

    handle(command) {
        if (command instanceof PlaceOrder) {
            const event = new OrderPlaced(command.aggregateId, command.commandData);
            this.eventStore.saveEvent(event);
        } else if (command instanceof ProcessPayment) {
            const event = new PaymentReceived(command.aggregateId, command.commandData);
            this.eventStore.saveEvent(event);
        } else if (command instanceof ShipOrder) {
            const event = new OrderShipped(command.aggregateId, command.commandData);
            this.eventStore.saveEvent(event);
        }
    }
}

// Aggregate Repository
class OrderRepository {
    constructor(eventStore) {
        this.eventStore = eventStore;
    }

    getById(id) {
        const order = new Order(id);
        const events = this.eventStore.getEventsForAggregate(id);
        events.forEach(event => order.applyEvent(event));
        return order;
    }
}

// Application Service
class OrderService {
    constructor(commandHandler, orderRepository) {
        this.commandHandler = commandHandler;
        this.orderRepository = orderRepository;
    }

    placeOrder(orderId, items, totalAmount) {
        const command = new PlaceOrder(orderId, { items, totalAmount });
        this.commandHandler.handle(command);
    }

    processPayment(orderId, paymentDetails) {
        const command = new ProcessPayment(orderId, paymentDetails);
        this.commandHandler.handle(command);
    }

    shipOrder(orderId, shippingDetails) {
        const command = new ShipOrder(orderId, shippingDetails);
        this.commandHandler.handle(command);
    }

    getOrderStatus(orderId) {
        const order = this.orderRepository.getById(orderId);
        return order.status;
    }
}

// Event Projector (for read models)
class OrderProjector {
    constructor(eventStore) {
        this.eventStore = eventStore;
        this.readModel = {};
    }

    projectAll() {
        this.eventStore.events.forEach(event => this.project(event));
    }

    project(event) {
        if (event instanceof OrderPlaced) {
            this.readModel[event.aggregateId] = {
                id: event.aggregateId,
                status: 'placed',
                items: event.eventData.items,
                totalAmount: event.eventData.totalAmount
            };
        } else if (event instanceof PaymentReceived) {
            this.readModel[event.aggregateId].status = 'paid';
        } else if (event instanceof OrderShipped) {
            this.readModel[event.aggregateId].status = 'shipped';
        }
    }

    getOrderSummary(orderId) {
        return this.readModel[orderId];
    }
}

// Usage example
function runExample() {
    const eventStore = new EventStore();
    const commandHandler = new CommandHandler(eventStore);
    const orderRepository = new OrderRepository(eventStore);
    const orderService = new OrderService(commandHandler, orderRepository);
    const orderProjector = new OrderProjector(eventStore);

    // Place an order
    const orderId = '12345';
    orderService.placeOrder(orderId, [{ productId: 'P1', quantity: 2 }], 100);

    // Process payment
    orderService.processPayment(orderId, { paymentMethod: 'credit_card' });

    // Ship order
    orderService.shipOrder(orderId, { address: '123 Main St' });

    // Get order status
    console.log('Order Status:', orderService.getOrderStatus(orderId));

    // Project events to read model
    orderProjector.projectAll();

    // Get order summary from read model
    console.log('Order Summary:', orderProjector.getOrderSummary(orderId));
}

runExample();

// Express API integration
const express = require('express');
const bodyParser = require('body-parser');

function createApi(orderService, orderProjector) {
    const app = express();
    app.use(bodyParser.json());

    app.post('/orders', (req, res) => {
        const orderId = Date.now().toString();
        const { items, totalAmount } = req.body;
        orderService.placeOrder(orderId, items, totalAmount);
        res.status(201).json({ orderId });
    });

    app.post('/orders/:orderId/payment', (req, res) => {
        const { orderId } = req.params;
        const paymentDetails = req.body;
        orderService.processPayment(orderId, paymentDetails);
        res.status(200).json({ message: 'Payment processed' });
    });

    app.post('/orders/:orderId/ship', (req, res) => {
        const { orderId } = req.params;
        const shippingDetails = req.body;
        orderService.shipOrder(orderId, shippingDetails);
        res.status(200).json({ message: 'Order shipped' });
    });

    app.get('/orders/:orderId', (req, res) => {
        const { orderId } = req.params;
        const orderSummary = orderProjector.getOrderSummary(orderId);
        if (orderSummary) {
            res.json(orderSummary);
        } else {
            res.status(404).json({ message: 'Order not found' });
        }
    });

    return app;
}

// Setup and run the API
const eventStore = new EventStore();
const commandHandler = new CommandHandler(eventStore);
const orderRepository = new OrderRepository(eventStore);
const orderService = new OrderService(commandHandler, orderRepository);
const orderProjector = new OrderProjector(eventStore);

const api = createApi(orderService, orderProjector);
const port = 3000;
api.listen(port, () => console.log(`API running on port ${port}`));
