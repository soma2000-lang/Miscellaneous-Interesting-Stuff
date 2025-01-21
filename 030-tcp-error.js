//example where pending callbacks are scheduled in a different phase. 
const net = require('net');
const fs = require(`fs`);
 
console.log(`START`);
// Define the IP and port
//change the host to a none existant port host, 
//the ECONNREFUSED will be queued in the pending callbacks phase output will be 
/*START
END
time out
Connection error: connect ECONNREFUSED 127.0.0.1:80
Connection closed
readFileCallback hello world
*/
//but if you change it to a valid ip/port say google's 
//the output will be 
/*
START
END
time out
readFileCallback hello world
Connected to server at 142.250.188.23:80
*/

 

// Create a client
const clientFail = new net.Socket();
const clientSuccess = new net.Socket();

// Connect to the server (fails)
clientFail.connect(9999,'192.168.4.21', () => {
    console.log(`Connected to server at ${'192.168.4.21'}:${9999}`);
});
// Connect to the server that exists (this is example.com)
clientSuccess.connect(80, '93.184.215.14', () => {
    console.log(`Connected to server at ${'93.184.215.14'}:${80}`);
});

// Handle errors
clientFail.on('error', (err) => {
    console.error(`Connection error: ${err.message}`);
});
// Handle errors
clientSuccess.on('error', (err) => {
    console.error(`Connection error: ${err.message}`);
});

 
//slow down the initial phase
for (let i = 1; i <= 500000000; i++);
//after the loop ends and initial phase is done, we enter the poll phase and actually read the file (no callbacks ready)
console.log(`END`);

