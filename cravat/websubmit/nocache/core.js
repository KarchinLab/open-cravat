'use strict';

function getEl(tag) {
    return document.createElement(tag);
}

function getTn(text) {
    return document.createTextNode(text);
}

function addEl(pelem, child) {
    pelem.appendChild(child);
    return pelem;
}

/***
 * Event handler for changing the currently displayed page. Attached to page tab click and sometimes called from other events.
 * @param selectedPageId - the name of the page to change to. valid options are 'storediv', 'submitdiv'
 */
function changePage (selectedPageId) {
    const pageSelect = document.getElementById('pageselect');
    const pageIdDivs = pageSelect.children;
    for (let i = 0; i < pageIdDivs.length; i++) {
        const pageIdDiv = pageIdDivs[i];
        const pageId = pageIdDiv.getAttribute('value');
        const page = document.getElementById(pageId);
        if (page.id === selectedPageId) {
            page.style.display = 'block';
            pageIdDiv.setAttribute('selval', 't');
            if (selectedPageId === 'storediv') {
                OC.currentTab = 'store';
            } else if (selectedPageId === 'submitdiv') {
                OC.currentTab = 'submit';
            }
        } else {
            page.style.display = 'none';
            pageIdDiv.setAttribute('selval', 'f');
        }
    }
}

/************** Mediator / PubSub ****************/
/***
 * PubSub is a simple publish / subscribe mediator pattern module to facilitate cross-module communication within the app.
 * A global mediator should be stored to the OC namespace, modules should subscribe to events they are interested in, then
 * other modules can publish to that event. The PubSub class has one event channel by default named 'error' and a default
 * handler for the 'error' event that will log the error arguments to the console.
 *
 * Example usage:
 * ```js
 * const mediator = new PubSub();
 * mediator.subscribe('error', showErrorDialog); // showErrorDialog would be an example hanlder function
 * mediator.publish('error', 'Test error', 'Error Details', 42); // publish an event on the 'error' channel; any number of args
 * mediator.subscribe('otherModuleChanged', updateHandler);
 * ```
 */
class PubSub {
    constructor() {
        this.channels = {};
        this.channels.error = [];
        this.channels.error.push(function(...args) {
            console.log(`Error: ${args}`);
        });
    }

    subscribe(channel, callback) {
        if (!this.channels.hasOwnProperty(channel)) {
            this.channels[channel] = [];
        }
        this.channels[channel].push(callback);
    }

    publish(channel, ...args) {
        if (!this.channels.hasOwnProperty(channel)) {
            this.channels[channel] = [];
        }
        for (let callback of this.channels[channel]) {
            callback(...args);
        }
    }
}
