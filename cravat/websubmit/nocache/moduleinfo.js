'use strict';
import {
    addClassRecursive, getSizeText, getEl, addEl,
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


function addLogo(moduleName, sdiv) {
    if (OC.storeLogos[moduleName] != undefined) {
        var img = OC.storeLogos[moduleName].cloneNode(true);
        addEl(sdiv, img);
        return img;
    }
    var moduleInfo = OC.remoteModuleInfo[moduleName];
    var img = null;
    if (moduleInfo.has_logo == true) {
        img = getEl('img');
        img.className = 'moduletile-logo';
        if (moduleInfo.uselocalonstore) {
            img.src = '/store/locallogo?module=' + moduleName;
        } else {
            img.src = OC.storeUrl + '/modules/' + moduleName + '/' + moduleInfo['latest_version'] + '/logo.png';
        }
        addEl(sdiv, img);
        OC.storeLogos[moduleName] = img;
    } else {
        sdiv.classList.add('moduletile-nologo');
        var span = getEl('div');
        span.className = 'moduletile-title';
        var title = moduleInfo.title;
        span.textContent = title
        if (title.length > 26) {
            span.style.fontSize = '30px';
        }
        addEl(sdiv, span);
    }
    return img;

}

function getModuleDetailInstallButton(moduleName, td, buttonDiv) {
    var button = getEl('button');
    button.id = 'installbutton';
    var localInfo = OC.localModuleInfo[moduleName];
    var buttonText = null;
    if (localInfo != undefined && localInfo.exists) {
        buttonText = 'Uninstall';
        button.style.backgroundColor = '#ffd3be';
        button.addEventListener('click', ()=>{
            OC.mediator.publish('moduleinfo.uninstall', moduleName);
            const storeDetailDiv = document.querySelector('#moduledetaildiv_store');
            if (storeDetailDiv !== null) storeDetailDiv.style.display = 'none';
        });
    } else {
        buttonText = 'Install';
        button.style.backgroundColor = '#beeaff';
        button.addEventListener('click', () => OC.mediator.publish('moduleinfo.install'));
    }
    button.textContent = buttonText;
    button.style.padding = '8px';
    button.style.fontSize = '18px';
    button.style.fontWeight = 'bold';
    button.setAttribute('module', moduleName);
    addEl(td, getEl('br'));
    return button;
}

function getModuleDetailUpdateButton(moduleName) {
    var button = getEl('button');
    button.id = 'updatebutton';
    button.style.backgroundColor = '#beeaff';
    button.textContent = 'Update';
    button.style.padding = '8px';
    button.style.fontSize = '18px';
    button.style.fontWeight = 'bold';
    button.setAttribute('module', moduleName);
    if (OC.updateConflicts.hasOwnProperty(moduleName)) {
        button.setAttribute('disabled', 'true');
        var blockList = [];
        for (let blockName in OC.updateConflicts[moduleName]) {
            blockList.push(blockName);
        }
        let blockString = blockList.join(', ');
        var titleText = 'Update blocked by: ' + blockString + '. Uninstall blocking modules to update.';
        button.setAttribute('title', titleText);
    }
    button.addEventListener('click', () => OC.mediator.publish('moduleinfo.update'));
    return button;
}

function makeModuleDetailDialog(moduleName, moduleListName, moduleListPos) {
    var mInfo = null;
    if (OC.currentTab == 'store') {
        if (OC.localModuleInfo[moduleName] != undefined && OC.localModuleInfo[moduleName].conf.uselocalonstore) {
            mInfo = OC.localModuleInfo[moduleName].conf;
        } else {
            mInfo = OC.remoteModuleInfo[moduleName];
        }
    } else if (OC.currentTab == 'submit') {
        mInfo = OC.localModuleInfo[moduleName];
        mInfo.latest_version = OC.remoteModuleInfo[moduleName]?.latest_version
    }
    var div = document.getElementById('moduledetaildiv_' + OC.currentTab);
    if (div) {
        emptyElement(div);
    } else {
        div = getEl('div');
        div.id = 'moduledetaildiv_' + OC.currentTab;
        div.className = 'moduledetaildiv';
    }
    if (moduleListName != null) {
        div.setAttribute('modulelistname', moduleListName);
    }
    if (moduleListPos != null) {
        div.setAttribute('modulelistpos', moduleListPos);
    }
    OC.currentDetailModule = moduleName;
    div.style.display = 'block';
    var table = getEl('table');
    table.style.height = '100px';
    table.style.border = '0px';
    table.style.width = 'calc(100% - 20px)';
    var tr = getEl('tr');
    tr.style.border = '0px';
    var td = getEl('td');
    td.style.border = '0px';
    var sdiv = getEl('div');
    sdiv.className = 'moduletile-logodiv';
    sdiv.style.width = '180px';
    sdiv.style.height = '85px';
    var img = addLogo(moduleName, sdiv);
    if (img != null) {
        img.style.maxHeight = '84px';
    } else {
        sdiv.style.position = 'relative';
        sdiv.children[0].style.display = 'none';
    }
    addEl(td, sdiv);
    addEl(tr, td);
    td = getEl('td');
    td.style.border = '0px';
    var span = getEl('div');
    span.style.fontSize = '30px';
    span.textContent = mInfo.title;
    addEl(td, span);
    addEl(td, getEl('br'));
    span = getEl('span');
    span.style.fontSize = '12px';
    span.style.color = 'green';
    span.textContent = mInfo.type;
    addEl(td, span);
    span = getEl('span');
    span.style.fontSize = '12px';
    span.style.color = 'green';
    span.textContent = ' | ' + mInfo.developer.organization;
    addEl(td, span);
    addEl(tr, td);
    td = getEl('td');
    td.style.border = '0px';
    td.style.verticalAlign = 'top';
    td.style.textAlign = 'right';
    var sdiv = getEl('div');
    var buttonDiv = getEl('div');
    if (OC.currentTab == 'store' && (OC.servermode == false || (OC.logged == true && OC.username == 'admin'))) {
        var button = getModuleDetailInstallButton(moduleName, td, buttonDiv);
        addEl(sdiv, button);
        addEl(td, sdiv);
        buttonDiv = sdiv;
        var sdiv = getEl('div');
        sdiv.id = 'installstatdiv_' + moduleName;
        sdiv.style.marginTop = '10px';
        sdiv.style.fontSize = '12px';
        if (OC.installInfo[moduleName] != undefined) {
            sdiv.textContent = OC.installInfo[moduleName]['msg'];
        }
        addEl(td, sdiv);
    } else if (OC.currentTab == 'submit') {
        var sdiv = getEl('div');
        sdiv.id = 'installstatdiv_' + moduleName;
        sdiv.style.marginTop = '10px';
        sdiv.style.fontSize = '12px';
        if (OC.installInfo[moduleName] != undefined) {
            sdiv.textContent = OC.installInfo[moduleName]['msg'];
        }
        addEl(td, sdiv);
    }
    addEl(tr, td);
    addEl(table, tr);
    addEl(div, table);
    addEl(div, getEl('hr'));
    // MD and maintainer
    table = getEl('table');
    table.style.height = 'calc(100% - 100px)';
    table.style.border = '0px';
    tr = getEl('tr');
    var tdHeight = (window.innerHeight * 0.8 - 150) + 'px';
    tr.style.border = '0px';
    td = getEl('td');
    td.style.border = '0px';
    td.style.width = '70%';
    td.style.verticalAlign = 'top';
    td.style.height = tdHeight;
    var mdDiv = getEl('div');
    mdDiv.style.height = '100%';
    mdDiv.style.overflow = 'auto';
    var wiw = window.innerWidth;
    mdDiv.style.maxWidth = (wiw * 0.8 * 0.68) + 'px';
    addEl(td, mdDiv);
    addEl(tr, td);
    $.get('/store/modules/' + moduleName + '/' + 'latest' + '/readme').done(function(data) {
        var protocol = window.location.protocol;
        var converter = new showdown.Converter({
            tables: true,
            openLinksInNewWindow: true
        });
        var mdhtml = converter.makeHtml(data);
        if (protocol == 'https:') {
            mdhtml = mdhtml.replace(/http:/g, 'https:');
        }
        var $mdhtml = $(mdhtml);
        var localRoot = window.location.origin + window.location.pathname.split('/').slice(0, -1).join('/');
        for (let img of $mdhtml.children('img')) {
            if (OC.currentTab == 'store') {
                var storeRoot = `${OC.systemConf.store_url}/modules/${moduleName}/${mInfo.latest_version}`
            } else if (OC.currentTab == 'submit') {
                var storeRoot = `/modules/annotators/${moduleName}`
            }
            img.src = img.src.replace(localRoot, storeRoot);
            img.style.display = 'block';
            img.style.margin = 'auto';
            img.style['max-width'] = '100%';
        }
        $(mdDiv).append($mdhtml);
        // output column description
        var d = getEl('div');
        d.id = 'moduledetail-output-column-div-' + OC.currentTab;
        d.style.display = 'none';
        var h2 = getEl('h2');
        h2.textContent = 'Output Columns';
        addEl(d, h2);
        var otable = getEl('table');
        otable.className = 'moduledetail-output-table';
        var othead = getEl('thead');
        var otr = getEl('tr');
        var oth = getEl('td');
        oth.textContent = 'Name';
        addEl(otr, oth);
        var oth = getEl('td');
        oth.textContent = 'Description';
        addEl(otr, oth);
        addEl(othead, otr);
        addEl(otable, othead);
        var otbody = getEl('tbody');
        otbody.id = 'moduledetail-' + OC.currentTab + '-output-tbody';
        addEl(otable, otbody);
        addEl(d, otable);
        addEl(mdDiv, d);
        addClassRecursive(mdDiv, 'moduledetaildiv-' + OC.currentTab + '-elem');
        if (OC.localModuleInfo[moduleName] != undefined && OC.localModuleInfo[moduleName].conf.uselocalonstore) {
            var data = mInfo;
            var otbody = document.getElementById('moduledetail-' + OC.currentTab + '-output-tbody');
            var outputColumnDiv = document.getElementById('moduledetail-output-column-div-' + OC.currentTab);
            var outputs = data['output_columns'];
            if (outputs != undefined) {
                var descs = [];
                for (var i1 = 0; i1 < outputs.length; i1++) {
                    var o = outputs[i1];
                    var desc = '';
                    if (o['desc'] != undefined) {
                        desc = o['desc'];
                    }
                    descs.push([o['title'], desc]);
                }
                if (descs.length > 0) {
                    outputColumnDiv.style.display = 'block';
                    for (var i1 = 0; i1 < descs.length; i1++) {
                        var title = descs[i1][0];
                        var desc = descs[i1][1];
                        var otr = getEl('tr');
                        var otd = getEl('td');
                        var ospan = getEl('span');
                        ospan.textContent = title;
                        addEl(otd, ospan);
                        addEl(otr, otd);
                        var otd = getEl('td');
                        var ospan = getEl('span');
                        ospan.textContent = desc;
                        addEl(otd, ospan);
                        addEl(otr, otd);
                        addEl(otbody, otr);
                    }
                }
            }
        } else {
            $.ajax({
                url: '/store/remotemoduleconfig',
                data: {
                    'module': moduleName
                },
                success: function(data) {
                    var otbody = document.getElementById('moduledetail-' + OC.currentTab + '-output-tbody');
                    var outputColumnDiv = document.getElementById('moduledetail-output-column-div-' + OC.currentTab);
                    var outputs = data['output_columns'];
                    if (outputs == undefined) {
                        return;
                    }
                    var descs = [];
                    for (var i1 = 0; i1 < outputs.length; i1++) {
                        var o = outputs[i1];
                        var desc = '';
                        if (o['desc'] != undefined) {
                            desc = o['desc'];
                        }
                        descs.push([o['title'], desc]);
                    }
                    if (descs.length > 0) {
                        outputColumnDiv.style.display = 'block';
                        for (var i1 = 0; i1 < descs.length; i1++) {
                            var title = descs[i1][0];
                            var desc = descs[i1][1];
                            var otr = getEl('tr');
                            var otd = getEl('td');
                            var ospan = getEl('span');
                            ospan.textContent = title;
                            addEl(otd, ospan);
                            addEl(otr, otd);
                            var otd = getEl('td');
                            var ospan = getEl('span');
                            ospan.textContent = desc;
                            addEl(otd, ospan);
                            addEl(otr, otd);
                            addEl(otbody, otr);
                        }
                    }
                },
            });
        }
    });
    // Information div
    td = getEl('td');
    td.style.width = '30%';
    td.style.border = '0px';
    td.style.verticalAlign = 'top';
    td.style.height = tdHeight;
    var infodiv = getEl('div');
    infodiv.id = 'moduledetaildiv-infodiv';
    infodiv.style.maxWidth = (wiw * 0.8 * 0.3) + 'px';
    var d = getEl('div');
    span = getEl('span');
    if (mInfo.commercial_warning) {
        span.textContent = mInfo.commercial_warning;
        span.style.color = 'red';
        span.style['font-weight'] = 'bold';
    }
    addEl(d, span);
    addEl(infodiv, d);
    var d = getEl('div');
    span = getEl('span');
    span.textContent = mInfo.description;
    addEl(d, span);
    addEl(infodiv, d);
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Module version: ';
    addEl(d, span);
    span = getEl('span');
    var remoteVersion = mInfo['latest_version'];
    span.textContent = remoteVersion;
    addEl(d, span);
    if (OC.currentTab == 'store' && OC.localModuleInfo[moduleName] != undefined) {
        var localVersion = OC.localModuleInfo[moduleName].version;
        if (localVersion != remoteVersion) {
            var span = getEl('span');
            span.textContent = ' (' + localVersion + ' installed)';
            addEl(d, span);
            if (mInfo.tags.indexOf('newavailable') >= 0) {
                addEl(d, getEl('br'));
                var span = getEl('span');
                span.style.color = 'red';
                span.textContent = 'Updates to your installed modules are available!';
                addEl(d, span);
                var button = getModuleDetailUpdateButton(moduleName);
                addEl(buttonDiv, button);
            }
        }
    }
    if (OC.currentTab == 'store') {
        addEl(infodiv, d);
        d = getEl('div');
        span = getEl('span');
        span.style.fontWeight = 'bold';
        span.textContent = 'Data source version: ';
        addEl(d, span);
        span = getEl('span');
        var datasource = mInfo['datasource'];
        if (datasource == null) {
            datasource = '';
        }
        span.textContent = datasource;
        addEl(d, span);
    }
    addEl(infodiv, d);
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Maintainer: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = mInfo['developer']['name'];
    addEl(d, span);
    addEl(d, getEl('br'));
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'e-mail: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = mInfo['developer']['email'];
    addEl(d, span);
    addEl(d, getEl('br'));
    addEl(infodiv, d);
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Citation: ';
    addEl(d, span);
    span = getEl('span');
    span.style.width = 'calc(100% - 120px)';
    span.style.wordWrap = 'break-word';
    span.style.verticalAlign = 'text-top';
    var citation = mInfo['developer']['citation'];
    if (citation != undefined && citation.startsWith('http')) {
        var a = getEl('a');
        a.href = citation;
        a.target = '_blank';
        a.textContent = citation;
        addEl(span, a);
    } else {
        span.textContent = citation;
    }
    addEl(d, span);
    addEl(infodiv, d);
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Organization: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = mInfo['developer']['organization'];
    addEl(d, span);
    addEl(infodiv, d);
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Website: ';
    addEl(d, span);
    span = getEl('a');
    span.textContent = mInfo['developer']['website'];
    span.href = mInfo['developer']['website'];
    span.target = '_blank';
    span.style.wordBreak = 'break-all';
    addEl(d, span);
    addEl(infodiv, d);
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Type: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = mInfo['type'];
    addEl(d, span);
    addEl(infodiv, d);
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Required modules: ';
    addEl(d, span);
    span = getEl('span');
    if (mInfo['requires'] != null) {
        span.textContent = mInfo['requires'];
    } else {
        span.textContent = 'None';
    }
    span.style.wordBreak = 'break-all';
    addEl(d, span);
    addEl(infodiv, d);
    if (OC.currentTab == 'store') {
        d = getEl('div');
        span = getEl('span');
        span.style.fontWeight = 'bold';
        span.textContent = 'Size: ';
        addEl(d, span);
        span = getEl('span');
        span.textContent = getSizeText(mInfo['size']);
        addEl(d, span);
        addEl(infodiv, d);
        d = getEl('div');
        span = getEl('span');
        span.style.fontWeight = 'bold';
        span.textContent = 'Posted on: ';
        addEl(d, span);
        span = getEl('span');
        var t = new Date(mInfo['publish_time']);
        span.textContent = t.toLocaleDateString();
        addEl(d, span);
        addEl(infodiv, d);
        d = getEl('div');
        span = getEl('span');
        span.style.fontWeight = 'bold';
        span.textContent = 'Downloads: ';
        addEl(d, span);
        span = getEl('span');
        var t = mInfo['downloads'];
        span.textContent = t;
        addEl(d, span);
        addEl(infodiv, d);
    }
    addEl(td, infodiv);
    addEl(tr, td);
    addEl(table, tr);
    addEl(div, table);
    var el = getEl('div');
    el.style.position = 'absolute';
    el.style.top = '0px';
    el.style.right = '0px';
    el.style.fontSize = '20px';
    el.style.padding = '10px';
    el.style.cursor = 'pointer';
    el.textContent = 'X';
    el.addEventListener('click', function(evt) {
        var pel = evt.target.parentElement;
        pel.parentElement.removeChild(pel);
    });
    addEl(div, el);
    addClassRecursive(div, 'moduledetaildiv-' + OC.currentTab + '-elem');
    OC.storeModuleDivClicked = true;
    return div;
}

export {
    getRemote,
    populateAnnotators,
    getLocal,
    enableStoreTabHead,
    disableStoreTabHead,
    updateRemoteModuleTagwithUpdate,
    updateModuleGroupInfo,
    makeInstalledGroup,
    makeModuleDetailDialog,
    addLogo
}