function getWs(){
	console.log('Get WebSockets Connection');
	// Create WebSocket connection.
	const socket = new WebSocket('ws://localhost:8080/ws');

	// Connection opened
	socket.addEventListener('open', function (event) {
	    setTimeout(function(){socket.send('Hello from the client!');},2500);
	});

	// Listen for messages
	socket.addEventListener('message', function (event) {
	    console.log(event.data);
	});
}

function sendTicks(socket) {
	console.log('Sending ticks');
	setTimeout(function(){},500);
	for (var i=0; i<5; i++) {
		msg = 'Client: '+i
		socket.send(msg);
		console.log(msg);
		setTimeout(function(){},1000);
	}
}

function run() {
	console.log('Run');
	getWs();
}