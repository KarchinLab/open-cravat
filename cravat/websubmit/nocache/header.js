// import * as core from './core'

var OC = OC || {};
if (!OC.mediator) {
    OC.mediator = new PubSub();
}

function addHeaderEventHandlers() {
    // on tab click, publish navigate event to mediator
    document.getElementById('submitdiv_tabhead').addEventListener('click', () => OC.mediator.publish('navigate', 'submitdiv'));
    document.getElementById('storediv_tabhead').addEventListener('click', () => OC.mediator.publish('navigate', 'storediv'));
    document.getElementById('admindiv_tabhead').addEventListener('click', () => OC.mediator.publish('navigate', 'admindiv'));
}

$(document).ready(() => addHeaderEventHandlers());