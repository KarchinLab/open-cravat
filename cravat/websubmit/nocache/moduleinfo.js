'use strict';
import {
    OC,
} from './core.js'

function populateAnnotators () {
    document.querySelector("#annotdivspinnerdiv").classList.remove("hide")
    document.querySelector("#annotator-group-select-div").classList.remove("show")
    return new Promise((resolve, reject) => {
        $.ajax({
            url:'/submit/annotators',
            type: 'GET',
            success: function (data) {
                document.querySelector("#annotdivspinnerdiv").classList.add("hide")
                document.querySelector("#annotator-group-select-div").classList.add("show")
                OC.GLOBALS.annotators = data;
				//TODO: remove timeout and see what breaks
                setTimeout(function () {
					OC.mediator.publish('moduleinfo.annotators');
                    resolve();
                }, 100);
            }
        })
    });
}

function getRemote() {
    $.ajax({
        url: '/store/remote',
        async: true,
        success: function(data) {
            OC.remoteModuleInfo = data['data'];
            OC.tagDesc = data['tagdesc'];
            for (var moduleName in OC.remoteModuleInfo) {
                var moduleInfo = OC.remoteModuleInfo[moduleName];
                if (!('tags' in moduleInfo) || moduleInfo['tags'] == null) {
                    moduleInfo.tags = [];
                }
                if (moduleInfo.type === 'package') {
                    moduleInfo.tags.push('package');
                }
            }
            var modules = Object.keys(OC.remoteModuleInfo);
            for (var i = 0; i < modules.length; i++) {
                var module = modules[i];
                var moduleInfo = OC.remoteModuleInfo[module];
                if (moduleInfo['queued'] == true) {
                    OC.installInfo[module] = {
                        'msg': 'queued'
                    };
                }
            }
            checkSystemReady();
        }
    });
}

function getLocal() {
    $.get('/store/local').done(function(data) {
        OC.localModuleInfo = data;
        updateModuleGroupInfo();
        makeInstalledGroup();
        if (OC.systemReadyObj.online) {
            enableStoreTabHead();
        } else {
            disableStoreTabHead();
        }
		OC.mediator.publish('moduleinfo.local');
        $.get('/store/updates').done(function(data) {
            OC.updates = data.updates;
            OC.updateConflicts = data.conflicts;
            OC.newModuleAvailable = false;
            updateModuleGroupInfo();
            updateRemoteModuleTagwithUpdate()
			OC.mediator.publish('moduleinfo.updates');
        });
    });
}

//TODO: find a more shared way to do enableStoreTabHead and disableStoreTabHead
function enableStoreTabHead() {
    document.getElementById('storediv_tabhead').setAttribute('disabled', 'f');
}

function disableStoreTabHead() {
    document.getElementById('storediv_tabhead').setAttribute('disabled', 't');
    document.getElementById('storediv_tabhead').classList.add('disabled');
    document.getElementById('storediv_tabhead').title = 'Internet connection not available';
}

function updateRemoteModuleTagwithUpdate() {
    var moduleNamesInInstallQueue = Object.keys(OC.installInfo);
    for (var remoteModuleName in OC.remoteModuleInfo) {
        var mI = OC.remoteModuleInfo[remoteModuleName];
        var tags = mI['tags'];
        if (tags == null) {
            tags = [];
            mI['tags'] = tags;
        }
        if (remoteModuleName in OC.localModuleInfo) {
            if (moduleNamesInInstallQueue.indexOf(remoteModuleName) == -1) {
                if (OC.updates[remoteModuleName] != undefined) {
                    var idx = tags.indexOf('newavailable');
                    if (idx == -1) {
                        tags.push('newavailable');
                    }
                    if (OC.baseModuleNames.includes(remoteModuleName) == false) {
                        OC.newModuleAvailable = true;
                    }
                } else {
                    var idx = tags.indexOf('newavailable');
                    if (idx >= 0) {
                        tags.splice(idx, 1);
                    }
                }
            }
        } else {
            var idx = tags.indexOf('installed');
            if (idx >= 0) {
                tags.splice(idx, 1);
            }
        }
    }
    for (var mn in OC.localModuleInfo) {
        var localModule = OC.localModuleInfo[mn];
        if (!('tags' in localModule)) {
            localModule['tags'] = [];
        }
        var remoteModule = OC.remoteModuleInfo[mn];
        if (remoteModule == undefined) {
            continue;
        }
        var localTags = localModule.tags;
        var remoteTags = remoteModule.tags;
        remoteModule.tags = remoteTags;
    }
}

function updateModuleGroupInfo() {
    OC.moduleGroupMembers = {};
    for (var mn in OC.remoteModuleInfo) {
        var groups = OC.remoteModuleInfo[mn]['groups'];
        if (groups != undefined && groups.length > 0) {
            for (var i = 0; i < groups.length; i++) {
                var group = groups[i];
                if (OC.remoteModuleInfo[group] == undefined && OC.localModuleInfo[group] == undefined) {
                    return;
                }
                if (OC.moduleGroupMembers[group] == undefined) {
                    OC.moduleGroupMembers[group] = [];
                }
                OC.moduleGroupMembers[group].push(mn);
            }
        }
    }
    for (var mn in OC.localModuleInfo) {
        var groups = OC.localModuleInfo[mn]['groups'];
        if (groups != undefined && groups.length > 0) {
            for (var i = 0; i < groups.length; i++) {
                var group = groups[i];
                if (OC.remoteModuleInfo[group] == undefined && OC.localModuleInfo[group] == undefined) {
                    return;
                }
                if (OC.moduleGroupMembers[group] == undefined) {
                    OC.moduleGroupMembers[group] = [];
                }
                if (OC.moduleGroupMembers[group].indexOf(mn) == -1) {
                    OC.moduleGroupMembers[group].push(mn);
                }
            }
        }
    }
    var groupNames = Object.keys(OC.moduleGroupMembers);
    for (var i = 0; i < groupNames.length; i++) {
        var gn = groupNames[i];
        var mns = OC.moduleGroupMembers[gn];
        var group = OC.remoteModuleInfo[gn];
        if (group == undefined) {
            group = OC.localModuleInfo[gn];
        }
        if (group == undefined) {
            delete OC.moduleGroupMembers[gn];
            continue;
        }
        for (var j = 0; j < mns.length; j++) {
            var mn = mns[j];
            var m = OC.remoteModuleInfo[mn];
            if (m === undefined) { // Work if no internet
                continue;
            }
            var d1 = new Date(group.publish_time);
            var d2 = new Date(m.publish_time);
            if (d1 < d2) {
                group.publish_time = m.publish_time;
            }
        }
    }
}

function makeInstalledGroup() {
    var localModules = Object.keys(OC.localModuleInfo);
    var groupNames = Object.keys(OC.moduleGroupMembers);
    OC.installedGroups = {};
    for (var i = 0; i < groupNames.length; i++) {
        var groupName = groupNames[i];
        var members = OC.moduleGroupMembers[groupName];
        for (var j = 0; j < members.length; j++) {
            var member = members[j];
            if (OC.localModuleInfo[member] != undefined) {
                if (OC.installedGroups[groupName] == undefined) {
                    OC.installedGroups[groupName] = [];
                }
                OC.installedGroups[groupName].push(member);
            }
        }
    }
}


function checkSystemReady() {
    $.ajax({
        url: '/issystemready',
        async: true,
        success: function(response) {
            var online = OC.systemReadyObj.online;
            OC.systemReadyObj = response;
            if (online != undefined) {
                OC.systemReadyObj.online = online;
            }
            if (OC.systemReadyObj.ready) {
                if (OC.servermode == false) {
                    OC.mediator.publish('populateJobs');
                }
                getLocal();
            } else {
                hidePageselect();
                showSystemModulePage();
            }
        },
    });
}

export {
    getRemote,
    populateAnnotators,
    getLocal,
    enableStoreTabHead,
    disableStoreTabHead,
    updateRemoteModuleTagwithUpdate,
    updateModuleGroupInfo,
    makeInstalledGroup
}