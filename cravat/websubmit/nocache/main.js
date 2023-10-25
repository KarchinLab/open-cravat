import * as core from './core.js';
import * as moduleInfo from './moduleinfo.js'
import * as submit from './websubmit.js';
import * as store from '../../store/nocache/webstore.js';
import * as header from './header.js';

// store.addMediatorEventHandlers();
$(document).ready(() => submit.websubmit_run());
// header.addHeaderEventHandlers();
