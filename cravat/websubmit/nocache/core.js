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
        if (page && page.id === selectedPageId) {
            page.style.display = '';
            pageIdDiv.setAttribute('selval', 't');
            if (selectedPageId === 'storediv') {
                OC.currentTab = 'store';
            } else if (selectedPageId === 'submitdiv') {
                OC.currentTab = 'submit';
            }
        } else {
            if (page) {
                page.style.display = 'none';
                pageIdDiv.setAttribute('selval', 'f');
            }
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


function titleCase(str) {
    return str.replace(
        /\w\S*/g,
        function(txt) {
            return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
        }
    );
}

function emptyElement(elem) {
    var last = null;
    while (last = elem.lastChild) {
        elem.removeChild(last);
    }
}

function checkVisible(elm) {
    // https://stackoverflow.com/questions/5353934/check-if-element-is-visible-on-screen
    var rect = elm.getBoundingClientRect();
    var viewHeight = Math.max(document.documentElement.clientHeight, window.innerHeight);
    return !(rect.bottom < 0 || rect.top - viewHeight >= 0);
}

function removeElementFromArrayByValue(a, e) {
    var idx = a.indexOf(e);
    if (idx >= 0) {
        a.splice(idx, 1);
    }
}

function prettyBytes(num, precision = 3, addSpace = true) {
    const UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
    if (Math.abs(num) < 1) return num + (addSpace ? ' ' : '') + UNITS[0];
    const exponent = Math.min(Math.floor(Math.log10(num < 0 ? -num : num) / 3), UNITS.length - 1);
    const n = Number(((num < 0 ? -num : num) / 1000 ** exponent).toPrecision(precision));
    return (num < 0 ? '-' : '') + n + (addSpace ? ' ' : '') + UNITS[exponent];
};

function getTimestamp() {
    var d = new Date()
    return "[" + d.getFullYear() + ":" + ("" + d.getMonth()).padStart(2, "0") + ":" + ("" + d.getDate()).padStart(2, "0") + " " + d.getHours() + ":" + ("" + d.getMinutes()).padStart(2, "0") + ":" + ("" + d.getSeconds()).padStart(2, "0") + "]"
}

function addClassRecursive(elem, className) {
    elem.classList.add(className);
    $(elem).children().each(
        function() {
            $(this).addClass(className);
            addClassRecursive(this, className);
        }
    );
}

function compareVersion(ver1, ver2) {
    var tok1 = ver1.split('.');
    var tok2 = ver2.split('.');
    var l = Math.min(tok1.length, tok2.length);
    for (var i = 0; i < l; i++) {
        var v1 = tok1[i];
        var v2 = tok2[i];
        var v1N = parseInt(v1);
        var v2N = parseInt(v2);
        if (isNaN(v1N) == false && isNaN(v2N) == false) {
            var diff = v1N - v2N;
            if (diff != 0) {
                return diff;
            }
        } else {
            if (v1 > v2) {
                return 1;
            } else if (v1 < v2) {
                return -1;
            }
        }
    }
    return tok1.length - tok2.length;
}

function getSizeText(size) {
    size = parseInt(size);
    if (size < 1024) {
        size = size + ' bytes';
    } else {
        size = size / 1024;
        if (size < 1024) {
            size = size.toFixed(0) + ' KB';
        } else {
            size = size / 1024;
            if (size < 1024) {
                size = size.toFixed(0) + ' MB';
            } else {
                size = size / 1024;
                size = size.toFixed(0) + ' GB';
            }
        }
    }
    return size;
}


/************** OC ****************/

const OC = {};
OC.mediator =   new PubSub();
export {
    getEl,
    getTn,
    addEl,
    changePage,
    PubSub,
    OC,
    titleCase,
    getSizeText,
    emptyElement,
    removeElementFromArrayByValue,
    addClassRecursive,
    prettyBytes,
    getTimestamp,
    compareVersion,
    checkVisible
};

