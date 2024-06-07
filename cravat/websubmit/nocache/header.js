'use strict';
import {
    getTn, addEl, getEl, OC
} from './core.js'

function addHeaderEventHandlers() {
    // on tab click, publish navigate event to mediator
    document.getElementById('submitdiv_tabhead').addEventListener('click', () => OC.mediator.publish('navigate', 'submitdiv'));
    document.getElementById('storediv_tabhead').addEventListener('click', () => OC.mediator.publish('navigate', 'storediv'));
    document.getElementById('admindiv_tabhead').addEventListener('click', () => OC.mediator.publish('navigate', 'admindiv'));

    // system update button
    document.getElementById('store-systemmoduleupdate-button').addEventListener('click', () => OC.mediator.publish('system.update'));

    document.getElementsByClassName('threedotsdiv')[0].addEventListener('click', onClickThreeDots);
    document.getElementById('help-menu-button').addEventListener('click', onHelpMenuClick);

    document.getElementById('system-conf-save-button').addEventListener('click', onClickSaveSystemConf);
    document.getElementById('system-conf-reset-button').addEventListener('click', resetSystemConf);
    document.getElementById('store-update-remote-button').addEventListener('click', onClickStoreUpdateRemoteButton);
}

$(document).ready(function() {
    addHeaderEventHandlers();
    OC.mediator.subscribe('showyesnodialog', showYesNoDialog);
});

function onClickStoreUpdateRemoteButton() {
    showUpdateRemoteSpinner();
    $.ajax({
        url: '/store/updateremote',
        success: function(response) {
            hideUpdateRemoteSpinner();
            moduleChange();
        },
    });
}

function onClickThreeDots (evt) {
    var div = document.getElementById('settingsdiv');
    var display = div.style.display;
    if (display == 'block') {
        display = 'none';
    } else {
        display = 'block';
    }
    div.style.display = display;
    document.getElementById('helpdiv').style.display = 'none';
    evt.stopPropagation();
}

function onHelpMenuClick(evt) {
    const helpDiv = document.getElementById('helpdiv');
    let display = helpDiv.style.display;
    if (display === 'flex') {
        display = 'none';
    } else {
        display = 'flex';
    }
    helpDiv.style.display = display;
    document.getElementById('settingsdiv').style.display = 'none';
    evt.stopPropagation();
}

function loadSystemConf () {
    $.get('/submit/getsystemconfinfo').done(function (response) {
        OC.systemConf = response.content;
        var s = document.getElementById('settings_save_metrics');
        if (OC.systemConf.save_metrics === 'empty') {
        	s.checked = true;
        } else {
        	s.checked = response['content']['save_metrics']
        }
        var s = document.getElementById('sysconfpathspan');
        s.value = response['path'];
        var s = document.getElementById('settings_jobs_dir_input');
        s.value = response['content']['jobs_dir'];
        var span = document.getElementById('server_user_span');
        if (! OC.servermode) {
            span.textContent = '/default';
        } else {
            span.textContent = '';
        }
        var s = document.getElementById('settings_modules_dir_input');
        s.value = response['content']['modules_dir'];
        var s = document.getElementById('settings_gui_input_size_limit');
        var cutoff = parseInt(response['content']['gui_input_size_limit']);
        s.value = cutoff;
        var s = document.getElementById('settings_max_num_concurrent_jobs');
        s.value = parseInt(response['content']['max_num_concurrent_jobs']);
        var s = document.getElementById('settings_max_num_concurrent_annotators_per_job');
        s.value = parseInt(response['content']['max_num_concurrent_annotators_per_job']);
    });
}

function resetSystemConf () {
    loadSystemConf();
}

function updateSystemConf (setMetrics) {
    $.get('/submit/getsystemconfinfo').done(function (response) {
        var s = document.getElementById('sysconfpathspan');
        response['path'] = s.value;
        var s = document.getElementById('settings_jobs_dir_input');
        response['content']['jobs_dir'] = s.value;
        var s = document.getElementById('settings_modules_dir_input');
        response['content']['modules_dir'] = s.value;
        var s = document.getElementById('settings_gui_input_size_limit');
        response['content']['gui_input_size_limit'] = parseInt(s.value);
        var s = document.getElementById('settings_max_num_concurrent_jobs');
        response['content']['max_num_concurrent_jobs'] = parseInt(s.value);
        var s = document.getElementById('settings_max_num_concurrent_annotators_per_job');
        response['content']['max_num_concurrent_annotators_per_job'] = parseInt(s.value);
        var s = document.getElementById('settings_save_metrics');
        var optout = false;
        if ((response['content']['save_metrics'] !== false) && (s.checked === false)) {
            optout = true;
        }
        response['content']['save_metrics'] = s.checked;
        $.ajax({
            url:'/submit/updatesystemconf',
            data: {'sysconf': JSON.stringify(response['content']), 'optout': optout},
            type: 'GET',
            success: function (response) {
                if (response['success'] == true) {
                	if (typeof setMetrics === 'undefined') {
	                    var mdiv = getEl('div');
	                    var span = getEl('span');
	                    span.textContent = 'System configuration has been updated.';
	                    addEl(mdiv, span);
	                    addEl(mdiv, getEl('br'));
	                    addEl(mdiv, getEl('br'));
	                    var justOk = true;
                        OC.mediator.publish('showyesnodialog', mdiv, null, false, justOk);
                	}
                } else {
                    var mdiv = getEl('div');
                    var span = getEl('span');
                    span.textContent = 'System configuration was not successful';
                    addEl(mdiv, span);
                    addEl(mdiv, getEl('br'));
                    addEl(mdiv, getEl('br'));
                    var span = getEl('span');
                    span.textContent = response['msg'];
                    addEl(mdiv, span);
                    addEl(mdiv, getEl('br'));
                    addEl(mdiv, getEl('br'));
                    var justOk = true;
                    OC.mediator.publish('showyesnodialog', mdiv, null, false, justOk);
                    return;
                }
                if (response['sysconf']['jobs_dir'] != undefined) {
                    populateJobs();
                    getLocal();
                    populateAnnotators();
                }
            }
        });
    });
}

function onClickSaveSystemConf () {
    document.getElementById('settingsdiv').style.display = 'none';
    updateSystemConf();
}

/**
 * YesNoDialog
 */
function showYesNoDialog(content, yescallback, noSpace, justOk) {
    var div = document.getElementById('yesnodialog');
    if (div != undefined) {
        $(div).remove();
    }
    var div = getEl('div');
    div.id = 'yesnodialog';
    if (typeof content === 'string') {
        content = getTn(content);
    }
    content.id = 'yesnodialog-contentdiv'
    addEl(div, content);
    addEl(div, getEl('br'));
    var btnDiv = getEl('div');
    if (justOk) {
        btnDiv.className = 'buttondiv';
        var btn = getEl('button');
        btn.textContent = 'Ok';
        btn.addEventListener('click', function(evt) {
            if (yescallback == undefined || yescallback == null) {
                $('#yesnodialog').remove();
            } else {
                $('#yesnodialog').remove();
                yescallback();
            }
        });
        addEl(btnDiv, btn);
    } else {
        btnDiv.className = 'buttondiv';
        var btn = getEl('button');
        btn.textContent = 'Yes';
        btn.addEventListener('click', function(evt) {
            $('#yesnodialog').remove();
            yescallback(true);
        });
        if (noSpace) {
            btn.disabled = true;
            btn.style.backgroundColor = '#e0e0e0';
        }
        addEl(btnDiv, btn);
        var btn = getEl('button');
        btn.textContent = 'No';
        btn.addEventListener('click', function(evt) {
            $('#yesnodialog').remove();
            yescallback(false);
        });
        addEl(btnDiv, btn);
    }
    addEl(div, btnDiv);
    addEl(document.body, div);
}

$(document).ready(() => addHeaderEventHandlers());

export { addHeaderEventHandlers, loadSystemConf, showYesNoDialog };