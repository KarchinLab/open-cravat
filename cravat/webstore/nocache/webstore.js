var currentDetailModule = null;
var remoteModuleInfo = {};
var origRemoteModuleInfo = null;
var localModuleInfo = {};
var updates = {};
var updateConflicts;
var filter = {};
var installQueue = [];
var installInfo = {};
var baseModuleNames = [];
var storeUrl = null;
var storeurl = $.get('/store/getstoreurl').done(function(response) {
    storeUrl = response;
});
var newModuleAvailable = false;
var baseModuleUpdateAvailable = false;
var storeFirstOpen = true;
var storeTileWidthStep = 294;
var modulesToIgnore = [
    'aggregator',
];
var storeLogos = {};
var moduleLists = {};
var baseToInstall = [];
var baseInstalled = false;
var defaultWidgetNames = [];
var uninstalledModules = [];
var moduleGroupMembers = {};
var currentPage = null;
var installedGroups = {};
var tagsCollected = [];
var tagDesc = {};

function getEl(tag){
	var new_node = document.createElement(tag);
	return new_node;
}

function getTn(text){
	var new_text_node = document.createTextNode(text);
	return new_text_node;
}

function addEl (pelem, child) {
	pelem.appendChild(child);
	return pelem;
}

function onClickStoreHome () {
    var homeButton = document.getElementById('store-home-button');
    if (homeButton.classList.contains('store-front-all-button-on')) {
        showAllModulesDiv();
        homeButton.classList.add('store-front-all-button-off');
        homeButton.classList.remove('store-front-all-button-on');
        updateFilter();
    } else if (homeButton.classList.contains('store-front-all-button-off')) {
        showStoreHome();
        homeButton.classList.add('store-front-all-button-on');
        homeButton.classList.remove('store-front-all-button-off');
        document.getElementById('store-tag-reset-button').classList.add('store-front-all-button-off');
        document.getElementById('store-tag-reset-button').classList.remove('store-front-all-button-on');
    }
}

function onClickStoreTagResetButton () {
    document.getElementById('store-namefilter').value = '';
    $('.store-tag-checkbox').each(function () {
        this.checked = false;
    });
    updateFilter();
    document.getElementById('store-home-button').classList.add('store-front-all-button-off');
    document.getElementById('store-home-button').classList.remove('store-front-all-button-on');
    document.getElementById('store-tag-reset-button').classList.add('store-front-all-button-on');
    document.getElementById('store-tag-reset-button').classList.remove('store-front-all-button-off');
}

function clickTab (value) {
    var tabs = document.getElementById('pageselect').children;
    for (var i = 0; i < tabs.length; i++) {
        var tab = tabs[i];
        if (tab.getAttribute('value') == value) {
            tab.click();
            return;
        }
    }
}

function hidePageselect () {
    document.getElementById('pageselect').style.display = 'none';
}

function showPageselect () {
    document.getElementById('pageselect').style.display = 'block';
}

function onClickInstallBaseComponents () {
    document.getElementById('store-systemmodule-msg-div').textContent = '';
    document.getElementById('store-systemmodule-install-button').disabled = true;
    installBaseComponents();
    document.getElementById('messagediv').style.display = 'none';
}

function showSystemModulePage () {
    document.getElementById('store-systemmodule-div').style.display = 'block';
    if (systemReadyObj.ready == false) {
        document.getElementById('store-systemmodule-systemnotready-div').style.display = 'block';
        var span = document.getElementById('store-systemmodule-systemnotready-span');
        var span2 = document.getElementById('store-systemmodule-systemnotready-span2');
        span.textContent = systemReadyObj['message'];
        if (systemReadyObj['code'] == 1) {
            span2.textContent = 'Please use the settings menu at top right to set the correct modules directory.';
        }
    } else {
        if (baseInstalled == false) {
            document.getElementById('store-systemmodule-missing-div').style.display = 'block';
        } else {
            document.getElementById('store-systemmodule-missing-div').style.display = 'none';
        }
        document.getElementById('store-systemmodule-update-div').style.display = 'none';
        if (baseToInstall.length == 0) {
            document.getElementById('store-systemmodule-install-button').disabled = true;
        }
    }
}

function hideSystemModulePage () {
    document.getElementById('store-systemmodule-div').style.display = 'none';
}

function getLocal () {
	$.get('/store/local').done(function(data){
        localModuleInfo = data;
        $.get('/store/updates').done(function(data){
            updates = data.updates;
            updateConflicts = data.conflicts;
            newModuleAvailable = false;
            var moduleNamesInInstallQueue = Object.keys(installInfo);
            for (var remoteModuleName in remoteModuleInfo) {
                var mI = remoteModuleInfo[remoteModuleName];
                var tags = mI['tags'];
                if (tags == null) {
                    tags = [];
                    mI['tags'] = tags;
                }
                if (remoteModuleName in localModuleInfo) {
                    if (localModuleInfo[remoteModuleName].exists) {
                        tags.push('installed');
                    }
                    if (moduleNamesInInstallQueue.indexOf(remoteModuleName) == -1) {
                        if (updates[remoteModuleName] != undefined) {
                            var idx = tags.indexOf('newavailable');
                            if (idx == -1) {
                                tags.push('newavailable');
                            }
                            if (baseModuleNames.includes(remoteModuleName) == false) {
                                newModuleAvailable = true;
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
            for (var mn in localModuleInfo) {
                var localModule = localModuleInfo[mn];
                if (! ('tags' in localModule)) {
                    localModule['tags'] = [];
                }
                var remoteModule = remoteModuleInfo[mn];
                if (remoteModule == undefined) {
                    continue;
                }
                var localTags = localModule.tags;
                var remoteTags = remoteModule.tags;
                for (var i = 0; i < localTags.length; i++) {
                    var tag = localTags[i];
                    if (remoteTags.indexOf(tag) == -1) {
                        remoteTags.push(tag);
                    }
                }
                remoteModule.tags = remoteTags;
            }
            for (var mn in remoteModuleInfo) {
                var groups = remoteModuleInfo[mn]['groups'];
                if (groups != undefined && groups.length > 0) {
                    for (var i = 0; i < groups.length; i++) {
                        var group = groups[i];
                        if (remoteModuleInfo[group] == undefined) {
                            return;
                        }
                        if (moduleGroupMembers[group] == undefined) {
                            moduleGroupMembers[group] = [];
                        }
                        moduleGroupMembers[group].push(mn);
                    }
                    remoteModuleInfo[mn]['groups'] = true;
                }
            }
            baseInstalled = true;
            var moduleNamesInInstallQueue = Object.keys(installInfo);
            baseToInstall = [];
            for (var i = 0; i < baseModuleNames.length; i++) {
                var baseModuleName = baseModuleNames[i];
                if (! (baseModuleName in localModuleInfo)) {
                    baseInstalled = false;
                    if (moduleNamesInInstallQueue.indexOf(baseModuleName) == -1) {
                        baseToInstall.push(baseModuleName);
                    }
                }
            }
            var div = document.getElementById('remotemodulepanels');
            if (div == null) {
                return;
            }
            if (origRemoteModuleInfo == null) {
                origRemoteModuleInfo = JSON.parse(JSON.stringify(remoteModuleInfo));
            }
            showOrHideSystemModuleUpdateButton();
            if (baseInstalled) {
                showPageselect();
                hideSystemModulePage();
                trimRemote();
                var div = document.getElementById('messagediv');
                div.style.display = 'none';
                div = document.getElementById('remotemodulepanels');
                var input = document.getElementById('store-namefilter');
                input.disabled = false;
                var div = document.getElementById('moduledetaildiv_store');
                if (div != null) {
                    if (div.style.display != 'none') {
                        makeModuleDetailDialog(currentDetailModule, null, null);
                    }
                }
                populateStoreHome();
                populateAllModulesDiv();
                var mg = document.getElementById('store-modulegroup-div').getAttribute('modulegroup');
                if (mg != undefined && mg != '') {
                    populateModuleGroupDiv(mg);
                }
                if (storeFirstOpen) {
                    showStoreHome();
                }
                storeFirstOpen = false;
            } else {
                hidePageselect();
                showSystemModulePage();
            }
            var d = document.getElementById('store-update-all-div');
            if (newModuleAvailable && (servermode == false || (logged == true && username == 'admin'))) {
                var modulesInInstallQueue = Object.keys(installInfo);
                d.style.display = 'block';
                announceStoreUpdateAllAvailable();
            } else {
                d.style.display = 'none';
            }
            populateStoreTagPanel();
            showOrHideInstallAllButton();
            showOrHideUpdateAllButton();
            showOrHideSystemModuleUpdateButton();
            if (systemReadyObj.online) {
                enableStoreTabHead();
            } else {
                disableStoreTabHead();
            }
            makeInstalledGroup();
            buildAnnotatorGroupSelector();
            populateAnnotators();
        });
    });
}

function makeInstalledGroup () {
    var localModules = Object.keys(localModuleInfo);
    var groupNames = Object.keys(moduleGroupMembers);
    installedGroups = {};
    for (var i = 0; i < groupNames.length; i++) {
        var groupName = groupNames[i];
        var members = moduleGroupMembers[groupName];
        for (var j = 0; j < members.length; j++) {
            var member = members[j];
            if (localModuleInfo[member] != undefined) {
                if (installedGroups[groupName] == undefined) {
                    installedGroups[groupName] = [];
                }
                installedGroups[groupName].push(member);
            }
        }
    }
}

function enableStoreTabHead () {
    document.getElementById('storediv_tabhead').setAttribute('disabled', 'f');
}

function disableStoreTabHead () {
    document.getElementById('storediv_tabhead').setAttribute('disabled', 't');
    document.getElementById('storediv_tabhead').classList.add('disabled');
    document.getElementById('storediv_tabhead').title = 'Internet connection not available';
}

function showOrHideSystemModuleUpdateButton () {
    if (servermode == false || (logged == true && username == 'admin')) {
        baseModuleUpdateAvailable = false;
        var moduleNames = Object.keys(updates);
        for (var i = 0; i < moduleNames.length; i++) {
            if (baseModuleNames.includes(moduleNames[i])) {
                baseModuleUpdateAvailable = true;
                break;
            }
        }
        var btn = document.getElementById('store-systemmoduleupdate-announce-div');
        if (baseModuleUpdateAvailable) {
            btn.style.display = 'inline-block';
        } else {
            btn.style.display = 'none';
        }
    }
}

function showOrHideInstallAllButton () {
    if (servermode == false || (logged == true && username == 'admin')) {
        var notInstalledModuleNames = getNotInstalledModuleNames();
        var div = document.getElementById('store-install-all-button');
        var display = null;
        if (notInstalledModuleNames.length == 0) {
            display = 'none';
        } else {
            display = 'inline-block';
        }
        div.style.display = display;
    }
}

function showOrHideUpdateAllButton () {
    if (servermode == false || (logged == true && username == 'admin')) {
        var modulesToUpdate = getModulesToUpdate();
        var div = document.getElementById('store-update-all-button');
        var display = null;
        if (modulesToUpdate.length == 0) {
            display = 'none';
        } else {
            display = 'inline-block';
        }
        div.style.display = display;
    }
}

function showStoreHome () {
    document.getElementById('store-home-div').style.display = 'block';
    document.getElementById('store-allmodule-div').style.display = 'none';
    document.getElementById('store-modulegroup-div').style.display = 'none';
}

function hideStoreHome () {
    document.getElementById('store-home-div').style.display = 'none';
    document.getElementById('store-allmodule-div').style.display = 'block';
    document.getElementById('store-modulegroup-div').style.display = 'none';
}

function showAllModulesDiv () {
    document.getElementById('store-home-div').style.display = 'none';
    document.getElementById('store-allmodule-div').style.display = 'block';
    document.getElementById('store-modulegroup-div').style.display = 'none';
}

function showStoreModuleGroup () {
    document.getElementById('store-home-div').style.display = 'none';
    document.getElementById('store-allmodule-div').style.display = 'none';
    document.getElementById('store-modulegroup-div').style.display = 'block';
}

function hideStoreModuleGroup () {
    document.getElementById('store-home-div').style.display = 'none';
    document.getElementById('store-allmodule-div').style.display = 'block';
    document.getElementById('store-modulegroup-div').style.display = 'none';
}

function onClickModuleGroupDivBackArrow (evt) {
    if (currentPage == 'store-home-div') {
        showStoreHome();
    } else if (currentPage == 'store-allmodule-div') {
        showAllModulesDiv();
    } else if (currentPage == 'store-modulegroup-div') {
        showStoreModuleGroup();
    }
}

function getMostDownloadedModuleNames () {
    var moduleNames = Object.keys(remoteModuleInfo);
    for (var i = 0; i < moduleNames.length; i++) {
        for (var j = i + 1; j < moduleNames.length - 1; j++) {
            var d1 = remoteModuleInfo[moduleNames[i]].downloads;
            var d2 = remoteModuleInfo[moduleNames[j]].downloads;
            if (d1 < d2) {
                var tmp = moduleNames[i];
                moduleNames[i] = moduleNames[j];
                moduleNames[j] = tmp;
            }
        }
    }
    var top10ModuleNames = [];
    var count = 0;
    for (var i = 0; i < moduleNames.length; i++) {
        var moduleName = moduleNames[i];
        if (moduleName == 'base') {
            continue;
        }
        if (baseModuleNames.indexOf(moduleName) >= 0) {
            continue;
        }
        if (remoteModuleInfo[moduleName].hidden == true) {
            continue;
        }
        if (remoteModuleInfo[moduleName].type == 'webviewerwidget' && defaultWidgetNames.includes(moduleName)) {
            continue;
        }
        top10ModuleNames.push(moduleName);
        count++;
        if (count == 10) {
            break;
        }
    }
    return top10ModuleNames;
}

function getNewestModuleNames () {
    var moduleNames = Object.keys(remoteModuleInfo);
    for (var i = 0; i < moduleNames.length; i++) {
        for (var j = i + 1; j < moduleNames.length - 1; j++) {
            var d1 = new Date(remoteModuleInfo[moduleNames[i]].publish_time);
            var d2 = new Date(remoteModuleInfo[moduleNames[j]].publish_time);
            if (d1 < d2) {
                var tmp = moduleNames[i];
                moduleNames[i] = moduleNames[j];
                moduleNames[j] = tmp;
            }
        }
    }
    var top10ModuleNames = [];
    var count = 0;
    for (var i = 0; i < moduleNames.length; i++) {
        var moduleName = moduleNames[i];
        if (moduleName == 'base') {
            continue;
        }
        if (baseModuleNames.indexOf(moduleName) >= 0) {
            continue;
        }
        if (remoteModuleInfo[moduleName].hidden == true) {
            continue;
        }
        if (remoteModuleInfo[moduleName].type == 'webviewerwidget' && defaultWidgetNames.includes(moduleName)) {
            continue;
        }
        top10ModuleNames.push(moduleName);
        count++;
        if (count == 10) {
            break;
        }
    }
    return top10ModuleNames;
}

function populateStoreHome () {
    // Most Downloaded
    var div = document.getElementById('store-home-featureddiv');
    $(div).empty();
    var sdiv = getEl('div');
    var featuredModules = getMostDownloadedModuleNames();
    moduleLists['download'] = featuredModules;
    sdiv.style.width = (featuredModules.length * storeTileWidthStep) + 'px';
    for (var i = 0; i < featuredModules.length; i++) {
        var panel = getRemoteModulePanel(featuredModules[i], 'download', i);
        addEl(sdiv, panel);
    }
    addEl(div, sdiv);
    // Newest
    var div = document.getElementById('store-home-newestdiv');
    $(div).empty();
    var sdiv = getEl('div');
    var newestModules = getNewestModuleNames();
    moduleLists['newest'] = newestModules;
    sdiv.style.width = (newestModules.length * storeTileWidthStep) + 'px';
    for (var i = 0; i < newestModules.length; i++) {
        var remoteModuleName = newestModules[i];
        var panel = null;
        if (remoteModuleInfo[remoteModuleName]['type'] != 'group') {
            panel = getRemoteModulePanel(remoteModuleName, 'newest', i);
        } else {
            panel = getRemoteModuleGroupPanel(remoteModuleName, 'newest', i);
        }
        addEl(sdiv, panel);
    }
    addEl(div, sdiv);
}

function onClickStoreHomeLeftArrow (el) {
    var d = el.nextElementSibling;
    var dw = d.offsetWidth;
    var s = d.scrollLeft;
    s -= Math.floor(dw / storeTileWidthStep) * storeTileWidthStep;
    $(d).animate({scrollLeft: s});
    //d.scrollLeft = s;
}

function onClickStoreHomeRightArrow (el) {
    var d = el.previousElementSibling;
    var dw = d.offsetWidth;
    var s = d.scrollLeft;
    s += Math.floor(dw / storeTileWidthStep) * storeTileWidthStep;
    $(d).animate({scrollLeft: s});
    //d.scrollLeft = s;
}

function trimRemote () {
    var remoteModuleNames = Object.keys(remoteModuleInfo);
    defaultWidgetNames = [];
    for (var i = 0; i < remoteModuleNames.length; i++) {
        var remoteModuleName = remoteModuleNames[i];
        var remoteModule = remoteModuleInfo[remoteModuleName];
        if (remoteModule.type == 'annotator') {
            defaultWidgetNames.push('wg' + remoteModuleName);
        }
    }
    for (var i = 0; i < remoteModuleNames.length; i++) {
        var remoteModuleName = remoteModuleNames[i];
        var remoteModule = remoteModuleInfo[remoteModuleName];
        if (remoteModule.tags == null) {
            remoteModule.tags = [];
        }
        if (modulesToIgnore.includes(remoteModuleName) && remoteModule.tags.includes('newavailable') == false){
            delete remoteModuleInfo[remoteModuleName];
            continue;
        }
        if (baseModuleNames.includes(remoteModuleName)) {
            delete remoteModuleInfo[remoteModuleName];
            if (remoteModule.tags.includes('newavailable')) {
                baseModuleUpdateAvailable = true;
            }
            continue;
        }
        var remoteModule = remoteModuleInfo[remoteModuleName];
        if (remoteModule.type == 'webviewerwidget' && 
                defaultWidgetNames.includes(remoteModuleName) && remoteModule.tags.includes('newavailable') == false) {
            delete remoteModuleInfo[remoteModuleName];
            continue;
        }
        if (remoteModule.hidden == true && remoteModule.tags.includes('newavailable') == false) {
            delete remoteModuleInfo[remoteModuleName];
            continue;
        }
    }
}

function checkSystemReady () {
    $.ajax({
        url: '/issystemready',
        async: true,
        success: function (response) {
            var online = systemReadyObj.online;
            systemReadyObj = response;
            if (online != undefined) {
                systemReadyObj.online = online;
            }
            if (systemReadyObj.ready) {
                getLocal();
            } else {
                hidePageselect();
                showSystemModulePage();
            }
        },
    });
}

function getRemote () {
	$.ajax({
        url: '/store/remote',
        async: true,
        success: function(data){
            remoteModuleInfo = data['data'];
            tagDesc = data['tagdesc'];
            for (var moduleName in remoteModuleInfo) {
                var moduleInfo = remoteModuleInfo[moduleName];
                if (! ('tags' in moduleInfo) || moduleInfo['tags'] == null) {
                    moduleInfo.tags = [];
                }
            }
            var modules = Object.keys(remoteModuleInfo);
            for (var i = 0; i < modules.length; i++) {
                var module = modules[i];
                var moduleInfo = remoteModuleInfo[module];
                if (moduleInfo['queued'] == true) {
                    installInfo[module] = {'msg': 'queued'};
                }
            }
            checkSystemReady();
        }
	});
}

function removeElementFromArrayByValue (a, e) {
    var idx = a.indexOf(e);
    if (idx >= 0) {
        a.splice(idx, 1);
    }
}

function getNotInstalledModuleNames () {
    var notInstalledModuleNames = [];
    for (var module in remoteModuleInfo) {
        var tags = remoteModuleInfo[module].tags;
        var installedTagFound = false;
        for (var i = 0; i < tags.length; i++) {
            var tag = tags[i];
            if (tag == 'installed') {
                installedTagFound = true;
                break;
            }
        }
        if (installedTagFound == false) {
            notInstalledModuleNames.push(module);
        }
    }
    return notInstalledModuleNames;
}

function populateStoreTagPanel () {
    tagsCollected = [];
    for (var module in remoteModuleInfo) {
        var tags = remoteModuleInfo[module].tags;
        for (var i = 0; i < tags.length; i++) {
            var tag = tags[i];
            if (tag == 'gene-level' || tag == 'variant-level') {
            }
            if (tagsCollected.indexOf(tag) == -1) {
                tagsCollected.push(tag);
            }
        }
    }
    removeElementFromArrayByValue(tagsCollected, 'installed');
    removeElementFromArrayByValue(tagsCollected, 'newavailable');
    tagsCollected.sort();
    var div = document.getElementById('store-tag-custom-div');
    $(div).empty();
    for (var i = 0; i < tagsCollected.length; i++) {
        var tag = tagsCollected[i];
        var label = getEl('label');
        label.className = 'checkbox-container';
        label.textContent = tag;
        if (tagDesc[tag] != undefined) {
            label.title = tagDesc[tag];
        }
        var input = getEl('input');
        input.type = 'checkbox';
        input.value = tag;
        input.className = 'store-tag-checkbox';
        input.addEventListener('click', function (evt) {
            onStoreTagCheckboxChange();
        });
        var span = getEl('span');
        span.className = 'checkmark';
        addEl(label, input);
        addEl(label, span);
        addEl(div, label);
    }
}

function installBaseComponents () {
    for (var i = 0; i < baseModuleNames.length; i++) {
        var module = baseModuleNames[i];
        if (localModuleInfo[module] == undefined || localModuleInfo[module]['exists'] == false) {
            queueInstall(module);
        }
    }
}

function emptyElement (elem) {
	var last = null;
    while (last = elem.lastChild) {
    	elem.removeChild(last);
    }
}

function updateFilter () {
    var nameinput = document.getElementById('store-namefilter');
    var nameStr = nameinput.value;
    filter = {};
    var filterHasValue = false;
    // Name filter
    if (nameStr != '') {
        filter['name'] = [nameStr];
        filterHasValue = true;
    }
    // Tag filter
    var checkboxes = $('.store-tag-checkbox:checked');
    var tags = [];
    for (var i = 0; i < checkboxes.length; i++) {
        tags.push(checkboxes[i].value);
        filterHasValue = true;
    }
    filter['tags'] = tags;
    populateAllModulesDiv();
    showAllModulesDiv();
    if (filterHasValue) {
        document.getElementById('store-tag-reset-button').classList.add('store-front-all-button-off');
        document.getElementById('store-tag-reset-button').classList.remove('store-front-all-button-on');
    } else {
        document.getElementById('store-tag-reset-button').classList.add('store-front-all-button-on');
        document.getElementById('store-tag-reset-button').classList.remove('store-front-all-button-off');
    }
    document.getElementById('store-home-button').classList.add('store-front-all-button-off');
    document.getElementById('store-home-button').classList.remove('store-front-all-button-on');
}

function onClickModuleTileAbortButton (evt) {
    var moduleName = evt.target.getAttribute('module');
    $.ajax({
        url: '/store/killinstall',
        data: {'module': moduleName},
        ajax: true,
        success: function (response) {
        }
    });
}

function onClickModuleTileInstallButton (evt) {
    var button = evt.target;
    var moduleName = button.getAttribute('module');
    var installSize = remoteModuleInfo[moduleName].size;
    $.ajax({
        url: '/store/freemodulesspace',
        ajax: true,
        success: function (response) {
            var freeSpace = response;
            var noSpace = false;
            if (installSize > freeSpace) {
                noSpace = true;
            }
            if (noSpace) {
                var mdiv = getEl('div');
                var span = getEl('span');
                span.textContent = 'Not enough space for installing the module!';
                addEl(mdiv, span);
                addEl(mdiv, getEl('br'));
                addEl(mdiv, getEl('br'));
                var justOk = true;
                showYesNoDialog(mdiv, null, noSpace, justOk);
                return;
            } else {
                queueInstall(moduleName);
                if (installQueue.length == 0) {
                    setModuleTileAbortButton(moduleName);
                } else {
                    setModuleTileUnqueueButton(moduleName);
                }
            }
        },
    });
}

function setModuleTileUnqueueButton (moduleName) {
    $('div.moduletile[module=' + moduleName + ']').each(function (i, div) {
        $(div).children('button').remove();
        var button = getModuleTileUnqueueButton(moduleName);
        addEl(div, button);
    });
}

function onClickModuleTileUnqueueButton (evt) {
    var moduleName = evt.target.getAttribute('module');
    $.ajax({
        url: '/store/unqueue',
        data: {'module': moduleName},
        ajax: true,
        success: function (response) {
        },
    });
}

function getModuleTileUnqueueButton (moduleName) {
    var button = getEl('button');
    button.className = 'modulepanel-unqueueinstall-button';
    button.textContent = 'Cancel download';
    button.setAttribute('module', moduleName);
    button.addEventListener('click', onClickModuleTileUnqueueButton);
    return button;
}

function onClickModuleTileUpdateButton (evt) {
    var button = evt.target;
    var moduleName = button.getAttribute('module');
    var installSize = updates[moduleName].size;
    $.ajax({
        url: '/store/freemodulesspace',
        ajax: true,
        success: function (response) {
            var freeSpace = response;
            var noSpace = false;
            if (installSize > freeSpace) {
                noSpace = true;
            }
            if (noSpace) {
                var mdiv = getEl('div');
                var span = getEl('span');
                span.textContent = 'Not enough space for updating the module!';
                addEl(mdiv, span);
                addEl(mdiv, getEl('br'));
                addEl(mdiv, getEl('br'));
                var justOk = true;
                showYesNoDialog(mdiv, null, noSpace, justOk);
                return;
            } else {
                queueInstall(moduleName, updates[moduleName].version);
                if (installQueue.length == 0) {
                    setModuleTileAbortButton(moduleName);
                } else {
                    setModuleTileUnqueueButton(moduleName);
                }
            }
        },
    });
}

function getModuleTileUpdateButton (moduleName) {
    var button = getEl('button');
    button.classList.add('butn');
    button.classList.add('modulepanel-update-button');
    button.textContent = 'UPDATE';
    button.setAttribute('module', moduleName);
    if (updateConflicts.hasOwnProperty(moduleName)) {
        button.setAttribute('disabled','true');
        var blockList = [];
        for (blockName in updateConflicts[moduleName]) {
            blockList.push(blockName);
        }
        blockString = blockList.join(', ');
        var titleText = 'Update blocked by: ' + blockString + '. Uninstall blocking modules to update.';
        button.setAttribute('title',titleText);
    }
    button.addEventListener('click', onClickModuleTileUpdateButton);
    return button;
}

function getModuleTileUninstallButton (moduleName) {
    var button = getEl('button');
    button.classList.add('butn');
    button.classList.add('modulepanel-uninstall-button');
    button.textContent = 'UNINSTALL';
    button.setAttribute('module', moduleName);
    button.addEventListener('click', function (evt) {
        var moduleName = evt.target.getAttribute('module');
        uninstallModule(moduleName);
    });
    return button;
}

function getModuleTileInstallButton (moduleName) {
    var div = getEl('div');
    div.classList.add('modulepanel-install-button-div');
    var button = getEl('button');
    button.classList.add('butn');
    button.classList.add('modulepanel-install-button');
    button.textContent = '\xa0INSTALL';
    button.setAttribute('module', moduleName);
    button.addEventListener('click', onClickModuleTileInstallButton);
    addEl(div, button);
    return div;
}

function getModuleTileAbortButton (moduleName) {
    var button = getEl('button');
    button.classList.add('butn');
    button.classList.add('modulepanel-stopinstall-button');
    button.textContent = 'Cancel download';
    button.setAttribute('module', moduleName);
    button.removeEventListener('click', onClickModuleTileInstallButton);
    button.addEventListener('click', onClickModuleTileAbortButton);
    return button;
}

function populateModuleGroupDiv (moduleGroupName) {
    document.getElementById('store-modulegroup-title-span').textContent = remoteModuleInfo[moduleGroupName]['title'];
    var div = document.getElementById('store-modulegroup-content-div');
    emptyElement(div);
    div.parentElement.setAttribute('modulegroup', moduleGroupName);
    var remoteModuleNames = moduleGroupMembers[moduleGroupName];
    if (remoteModuleNames == undefined) {
        var panel = getEl('div');
        panel.classList.add('no-group-member-msg-div');
        panel.textContent = 'No module in this group';
        addEl(div, panel);
    } else {
        moduleLists['modulegroup'] = remoteModuleNames;
        for (var i = 0; i < remoteModuleNames.length; i++) {
            var remoteModuleName = remoteModuleNames[i];
            var remoteModule = remoteModuleInfo[remoteModuleName];
            var panel = null;
            if (remoteModule['type'] != 'group') {
                panel = getRemoteModulePanel(remoteModuleName, 'modulegroup', i);
            } else {
                panel = getRemoteModuleGroupPanel(remoteModuleName, 'modulegroup', i);
            }
            addEl(div, panel);
        }
    }
}

function saveCurrentPage () {
    var divIds = ['store-home-div', 'store-allmodule-div', 'store-modulegroup-div'];
    for (var i = 0; i < divIds.length; i++) {
        var divId = divIds[i];
        if (document.getElementById(divId).style.display != 'none') {
            currentPage = divId;
            break;
        }
    }
}

function getRemoteModuleGroupPanel (moduleName, moduleListName, moduleListPos) {
    var moduleInfo = remoteModuleInfo[moduleName];
    var div = getEl('div');
    div.className = 'moduletile';
    div.classList.add('modulegroup');
    div.setAttribute('module', moduleName);
    div.setAttribute('modulelistname', moduleListName);
    div.setAttribute('modulelistpos', moduleListPos);
    div.setAttribute('moduletype', moduleInfo.type);
    var sdiv = getEl('div');
    sdiv.id = 'logodiv_' + moduleName;
    sdiv.className = 'moduletile-logodiv';
    sdiv.setAttribute('module', moduleName);
    sdiv.onclick = function (evt) {
        var target = evt.target;
        if (target.classList.contains('moduletile-title')) {
            target = target.parentElement;
        }
        var moduleName = target.getAttribute('module');
        saveCurrentPage();
        populateModuleGroupDiv(moduleName);
        showStoreModuleGroup();
        evt.stopPropagation();
    }
    var img = addLogo(moduleName, sdiv);
    if (img != null) {
        img.onclick = function (evt) {
            var moduleName = evt.target.parentElement.getAttribute('module');
            saveCurrentPage();
            populateModuleGroupDiv(moduleName);
            showStoreModuleGroup();
            evt.stopPropagation();
        }
    }
    addEl(div, sdiv);
    var span = null;
    span = getEl('div');
    span.className = 'modulepanel-title-span';
    var moduleTitle = moduleInfo.title;
    if (moduleTitle.length > 24) {
        span.style.fontSize = '14px';
    }
    addEl(span, getTn(moduleInfo.title));
    addEl(div, span);
    span = getEl('span');
    span.className = 'modulepanel-datasource-span';
    var datasource = moduleInfo['datasource'];
    if (datasource == null) {
        datasource = '';
    }
    span.textContent = datasource;
    span.title = 'Data source version';
    addEl(div, span);
    addEl(div, sdiv);
    addEl(div, getEl('br'));
    if (moduleInfo.type != 'annotator') {
        var t = moduleInfo.type;
        if (t == 'webviewerwidget') {
            t = 'Widget';
        } else {
            t = t.charAt(0).toUpperCase() + t.slice(1);
        }
        var sdiv = getEl('div');
        sdiv.className = 'moduletile-typediv';
        sdiv.textContent = t;
        addEl(div, sdiv);
    }
    var members = moduleGroupMembers[moduleName];
    var updateAvail = false;
    if (members != undefined) {
        for (var i = 0; i < members.length; i++) {
            var member = members[i];
            if (remoteModuleInfo[member].tags.indexOf('newavailable') != -1) {
                updateAvail = true;
                break;
            }
        }
    }
    if (updateAvail && (servermode == false || (logged == true && username == 'admin'))) {
        var span = getEl('span');
        span.className = 'moduletile-group-updateavailable-span';
        span.textContent = 'Update available';
        addEl(div, span);
    }
    return div
}

function getRemoteModulePanel (moduleName, moduleListName, moduleListPos) {
    var moduleInfo = remoteModuleInfo[moduleName];
    var div = getEl('div');
    div.className = 'moduletile';
    div.setAttribute('module', moduleName);
    div.setAttribute('modulelistname', moduleListName);
    div.setAttribute('modulelistpos', moduleListPos);
    div.setAttribute('moduletype', moduleInfo.type);
    var sdiv = getEl('div');
    sdiv.id = 'logodiv_' + moduleName;
    sdiv.className = 'moduletile-logodiv';
    sdiv.setAttribute('module', moduleName);
    sdiv.onclick = function (evt) {
        var moduleName = this.getAttribute('module');
        var panel = this.parentElement;
        var moduleListName = panel.getAttribute('modulelistname');
        var moduleListPos = panel.getAttribute('modulelistpos');
        var dialog = makeModuleDetailDialog(moduleName, moduleListName, moduleListPos);
        var storediv = document.getElementById('storediv');
        addEl(storediv, dialog);
        evt.stopPropagation();
    }
    var img = addLogo(moduleName, sdiv);
    if (img != null) {
        img.onclick = function (evt) {
            var panel = evt.target.parentElement.parentElement;
            var moduleListName = panel.getAttribute('modulelistname');
            var moduleListPos = panel.getAttribute('modulelistpos');
            var moduleName = div.getAttribute('module');
            var storediv = document.getElementById('storediv');
            var dialog = makeModuleDetailDialog(moduleName, moduleListName, moduleListPos);
            addEl(storediv, dialog);
            evt.stopPropagation();
        }
    }
    addEl(div, sdiv);
    var span = null;
    span = getEl('div');
    span.style.height = '5px';
    addEl(div, span);
    span = getEl('div');
    span.className = 'modulepanel-title-span';
    var moduleTitle = moduleInfo.title;
    if (moduleTitle.length > 24) {
        span.style.fontSize = '14px';
    }
    addEl(span, getTn(moduleInfo.title));
    addEl(div, span);
    var sdiv = getEl('div');
    sdiv.className = 'modulepanel-typesizedate-div';
    span = getEl('span');
    span.className = 'modulepanel-size-span';
    span.textContent = getSizeText(moduleInfo['size']);
    span.title = 'module size';
    addEl(sdiv, span);
    span = getEl('span');
    span.className = 'modulepanel-datasource-span';
    var datasource = moduleInfo['datasource'];
    if (datasource == null) {
        datasource = '';
    }
    span.textContent = datasource;
    span.title = 'Data source version';
    addEl(div, span);
    addEl(div, sdiv);
    addEl(div, getEl('br'));
    var installStatus = '';
    var btnAddedFlag = false;
    if (installInfo[moduleName] != undefined) {
        var msg = installInfo[moduleName]['msg'];
        if (msg == 'uninstalling') {
            installStatus = 'Uninstalling...';
        } else if (msg == 'installing') {
            installStatus = 'Installing...';
        } else if (msg == 'queued') {
            installStatus = 'Queued';
        } else if (msg.includes('Downloading') || 
                msg.includes('Start install') || 
                msg.includes('Extracting') ||
                msg.includes('Verifying')) {
            installStatus = 'Installing...';
        }
    } else {
        if (localModuleInfo[moduleName] != undefined && localModuleInfo[moduleName]['exists']) {
            installStatus = 'Installed';
        } else {
            installStatus = '';
        }
    }
    var progSpan = getEl('div');
    progSpan.id = 'panelinstallprogress_' + moduleName;
    progSpan.className = 'panelinstallprogressspan';
    if (installInfo[moduleName] != undefined && installStatus == 'Installing...') {
        progSpan.textContent = installInfo[moduleName]['msg'];
    }
    addEl(div, progSpan);
    var span = getEl('div');
    span.id = 'panelinstallstatus_' + moduleName;
    addEl(div, span);
    if (servermode == false || (logged == true && username == 'admin')) {
        if (installStatus == 'Queued') {
            var button = getModuleTileUnqueueButton(moduleName);
            addEl(div, button);
        } else if (installStatus == 'Installing...') {
            var button = getModuleTileAbortButton(moduleName);
            addEl(div, button);
        } else if (installStatus == 'Installed') {
            if (remoteModuleInfo[moduleName].tags.indexOf('newavailable') >= 0) {
                var button = getModuleTileUpdateButton(moduleName);
                addEl(div, button);
            } else {
                var button = getModuleTileUninstallButton(moduleName);
                addEl(div, button);
            }
        } else {
            var tags = remoteModuleInfo[moduleName].tags;
            if (tags.indexOf('installed') >= 0) {
                var button = getModuleTileUninstallButton(moduleName);
                addEl(div, button);
            } else {
                var button = getModuleTileInstallButton(moduleName);
                addEl(div, button);
                uninstalledModules.push(moduleName);
            }
        }
    }
    if (moduleInfo.type != 'annotator') {
        var t = moduleInfo.type;
        if (t == 'webviewerwidget') {
            t = 'Widget';
        } else {
            t = t.charAt(0).toUpperCase() + t.slice(1);
        }
        var sdiv = getEl('div');
        sdiv.className = 'moduletile-typediv';
        sdiv.textContent = t;
        addEl(div, sdiv);
    }
    return div
}

function getFilteredRemoteModules () {
    var filteredRemoteModules = {};
    var remoteModuleNames = Object.keys(remoteModuleInfo);
    var hasFilter = Object.keys(filter).length > 0;
    for (var i = 0; i < remoteModuleNames.length; i++) {
        var remoteModuleName = remoteModuleNames[i];
        var remoteModuleNameLower = remoteModuleName.toLowerCase();
        var remoteModule = remoteModuleInfo[remoteModuleName];
        var newCheck = document.getElementById('store-tag-checkbox-newavailable').checked;
        if (remoteModule['groups'] == true) {
            var pass = false;
            if (currentPage == 'storediv-modulegroup-div') {
                pass = true;
            } else if (remoteModule['tags'].indexOf('newavailable') != -1 && newCheck == true) {
                pass = true;
            }
            if (pass == false) {
                continue;
            }
        }
        if (hasFilter) {
            var typeYes = false;
            var nameYes = false;
            var tagYes = false;
            typeYes = true;
            if (filter['name'] != undefined && filter['name'] != '') {
                for (var j = 0; j < filter['name'].length; j++) {
                    var queryStr = filter['name'][j].toLowerCase();
                    if (remoteModule['title'].toLowerCase().includes(queryStr) || remoteModule['description'].toLowerCase().includes(queryStr)) {
                        nameYes = true;
                        break;
                    }
                }
            } else {
                nameYes = true;
            }
            if (filter['tags'] != undefined && filter['tags'].length > 0) {
                var checkbox = document.getElementById('store-tag-andor-checkbox');
                var op = 'and';
                if (checkbox.checked) {
                    op = 'or';
                }
                if (op == 'and') {
                    tagYes = true;
                    for (var j = 0; j < filter['tags'].length; j++) {
                        if (remoteModule['tags'].indexOf(filter['tags'][j]) == -1) {
                            tagYes = false;
                            break;
                        }
                    }
                } else if (op == 'or') {
                    tagYes = false;
                    for (var j = 0; j < filter['tags'].length; j++) {
                        if (remoteModule['tags'].indexOf(filter['tags'][j]) >= 0) {
                            tagYes = true;
                            break;
                        }
                    }
                }
            } else {
                tagYes = true;
            }
        } else {
            typeYes = true;
            nameYes = true;
            tagYes = true;
        }
        if (typeYes && nameYes && tagYes) {
            filteredRemoteModules[remoteModuleName] = remoteModule;
        }
    }
    return filteredRemoteModules;
}

function getSortedFilteredRemoteModuleNames () {
    var sel = document.getElementById('store-sort-select');
    var option = sel.options[sel.selectedIndex];
    var sortKey = option.value;
    var filteredRemoteModules = getFilteredRemoteModules();
    var sortedNames = null;
    if (sortKey == 'name') {
        sortedNames = Object.keys(filteredRemoteModules);
        for (var i = 0; i < sortedNames.length - 1; i++) {
            for (var j = i + 1; j < sortedNames.length; j++) {
                var t1 = filteredRemoteModules[sortedNames[i]].title;
                var t2 = filteredRemoteModules[sortedNames[j]].title;
                if (t1.localeCompare(t2) > 0) {
                    var tmp = sortedNames[i];
                    sortedNames[i] = sortedNames[j];
                    sortedNames[j] = tmp;
                }
            }
        }
    } else if (sortKey == 'size') {
        sortedNames = Object.keys(filteredRemoteModules);
        for (var i = 0; i < sortedNames.length - 1; i++) {
            for (var j = i + 1; j < sortedNames.length; j++) {
                var size1 = filteredRemoteModules[sortedNames[i]].size;
                var size2 = filteredRemoteModules[sortedNames[j]].size;
                if (size1 < size2) {
                    var tmp = sortedNames[i];
                    sortedNames[i] = sortedNames[j];
                    sortedNames[j] = tmp;
                }
            }
        }
    } else if (sortKey == 'date') {
        sortedNames = Object.keys(filteredRemoteModules);
        for (var i = 0; i < sortedNames.length - 1; i++) {
            for (var j = i + 1; j < sortedNames.length; j++) {
                var v1 = filteredRemoteModules[sortedNames[i]].publish_time;
                var v2 = filteredRemoteModules[sortedNames[j]].publish_time;
                v1 = new Date(v1);
                v2 = new Date(v2);
                if (v1 < v2) {
                    var tmp = sortedNames[i];
                    sortedNames[i] = sortedNames[j];
                    sortedNames[j] = tmp;
                }
            }
        }
    }
    return sortedNames;
}

function populateAllModulesDiv (group) {
    var div = document.getElementById('remotemodulepanels');
    emptyElement(div);
    var remoteModuleNames = getSortedFilteredRemoteModuleNames();
    moduleLists['all'] = remoteModuleNames;
    for (var i = 0; i < remoteModuleNames.length; i++) {
        var remoteModuleName = remoteModuleNames[i];
        var remoteModule = remoteModuleInfo[remoteModuleName];
        if (group == 'basetoinstall') {
            if (baseModuleNames.indexOf(remoteModuleName) == -1) {
                continue;
            }
            if (remoteModule.tags.indexOf('installed') > -1) {
                continue;
            }
        } else {
            if (remoteModuleName == 'example_annotator' || remoteModuleName == 'template') {
                continue;
            }
        }
        var panel = null;
        if (remoteModule['type'] != 'group') {
            panel = getRemoteModulePanel(remoteModuleName, 'all', i);
        } else {
            panel = getRemoteModuleGroupPanel(remoteModuleName, 'all', i);
        }
        addEl(div, panel);
    }
}

function addLogo (moduleName, sdiv) {
    if (storeLogos[moduleName] != undefined) {
        var img = storeLogos[moduleName].cloneNode(true);
        addEl(sdiv, img);
        return img;
    }
    var moduleInfo = remoteModuleInfo[moduleName];
    var img = null;
    if (moduleInfo.has_logo == true) {
        img = getEl('img');
        img.className = 'moduletile-logo';
        img.src = storeUrl + '/modules/' + moduleName + '/' + moduleInfo['latest_version'] + '/logo.png';
        addEl(sdiv, img);
        storeLogos[moduleName] = img;
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

function onClicModuleDetailAbortButton (evt) {
    var moduleName = evt.target.getAttribute('module');
    $.ajax({
        url: '/store/killinstall',
        data: {'module': moduleName},
        ajax: true,
    });
}

function onClickModuleDetailUpdateButton (evt) {
    var btn = evt.target;
    var btnModuleName = btn.getAttribute('module');
    var installSize = updates[btnModuleName].size;
    $.ajax({
        url: '/store/freemodulesspace',
        ajax: true,
        success: function (response) {
            var freeSpace = response;
            var noSpace = false;
            if (installSize > freeSpace) {
                noSpace = true;
            }
            if (noSpace) {
                var mdiv = getEl('div');
                var span = getEl('span');
                span.textContent = 'Not enough space for updating the module!';
                addEl(mdiv, span);
                addEl(mdiv, getEl('br'));
                addEl(mdiv, getEl('br'));
                var justOk = true;
                showYesNoDialog(mdiv, null, noSpace, justOk);
                return;
            } else {
                var buttonText = null;
                if (installQueue.length == 0) {
                    buttonText = 'Updating...';
                } else {
                    buttonText = 'Queued';
                }
                queueInstall(btnModuleName, updates[btnModuleName].version);
                btn.textContent = buttonText;
                btn.style.color = 'red';
                document.getElementById('moduledetaildiv_store').style.display = 'none';
                if (installQueue.length == 0) {
                    setModuleTileAbortButton(btnModuleName);
                } else {
                    setModuleTileUnqueueButton(btnModuleName);
                }
            }
        },
    });
}

function getModuleDetailUpdateButton (moduleName) {
    var button = getEl('button');
    button.id = 'updatebutton';
    button.style.backgroundColor = '#beeaff';
    button.textContent = 'Update';
    button.style.padding = '8px';
    button.style.fontSize = '18px';
    button.style.fontWeight = 'bold';
    button.setAttribute('module', moduleName);
    if (updateConflicts.hasOwnProperty(moduleName)) {
        button.setAttribute('disabled','true');
        var blockList = [];
        for (blockName in updateConflicts[moduleName]) {
            blockList.push(blockName);
        }
        blockString = blockList.join(', ');
        var titleText = 'Update blocked by: ' + blockString + '. Uninstall blocking modules to update.';
        button.setAttribute('title',titleText);
    }
    button.addEventListener('click', onClickModuleDetailUpdateButton);
    return button;
}

function onClickModuleDetailInstallButton (evt) {
    $.ajax({
        url: '/store/freemodulesspace',
        ajax: true,
        success: function (response) {
            var freeSpace = response;
            var btn = evt.target;
            var btnModuleName = btn.getAttribute('module');
            var installSize = remoteModuleInfo[btnModuleName].size;
            var noSpace = false;
            if (installSize > freeSpace) {
                noSpace = true;
            }
            if (noSpace) {
                var mdiv = getEl('div');
                var span = getEl('span');
                span.textContent = 'Not enough space for installing the module!';
                addEl(mdiv, span);
                addEl(mdiv, getEl('br'));
                addEl(mdiv, getEl('br'));
                var justOk = true;
                showYesNoDialog(mdiv, null, noSpace, justOk);
                return;
            } else {
                var buttonText = null;
                if (installQueue.length == 0) {
                    buttonText = 'Installing...';
                } else {
                    buttonText = 'Queued';
                }
                queueInstall(btnModuleName);
                btn.textContent = buttonText;
                btn.style.color = 'red';
                document.getElementById('moduledetaildiv_store').style.display = 'none';
                var moduleName = btn.getAttribute('module');
                if (installQueue.length == 0) {
                    setModuleTileAbortButton(moduleName);
                } else {
                    setModuleTileUnqueueButton(moduleName);
                }
            }
        },
    });
}

function onClickModuleDetailUninstallButton (evt) {
    var btn = evt.target;
    btn.textContent = 'Uninstalling...';
    btn.style.color = 'red';
    uninstallModule(btn.getAttribute('module'));
    document.getElementById('moduledetaildiv_store').style.display = 'none';
}

function getModuleDetailInstallButton (moduleName, td, buttonDiv) {
    var button = getEl('button');
    button.id = 'installbutton';
    var localInfo = localModuleInfo[moduleName];
    var buttonText = null;
    if (localInfo != undefined && localInfo.exists) {
        buttonText = 'Uninstall';
        button.style.backgroundColor = '#ffd3be';
        button.addEventListener('click', onClickModuleDetailUninstallButton);
    } else {
        buttonText = 'Install';
        button.style.backgroundColor = '#beeaff';
        button.addEventListener('click', onClickModuleDetailInstallButton);
    }
    button.textContent = buttonText;
    button.style.padding = '8px';
    button.style.fontSize = '18px';
    button.style.fontWeight = 'bold';
    button.setAttribute('module', moduleName);
    addEl(td, getEl('br'));
    return button;
}

function makeModuleDetailDialog (moduleName, moduleListName, moduleListPos) {
    var mInfo = null;
    if (currentTab == 'store') {
        mInfo = remoteModuleInfo[moduleName];
    } else if (currentTab == 'submit') {
        mInfo = localModuleInfo[moduleName];
    }
    var div = document.getElementById('moduledetaildiv_' + currentTab);
    if (div) {
        emptyElement(div);
    } else {
        div = getEl('div');
        div.id = 'moduledetaildiv_' + currentTab;
        div.className = 'moduledetaildiv';
    }
    if (moduleListName != null) {
        div.setAttribute('modulelistname', moduleListName);
    }
    if (moduleListPos != null) {
        div.setAttribute('modulelistpos', moduleListPos);
    }
    currentDetailModule = moduleName;
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
    if (currentTab == 'store' && (servermode == false || (logged == true && username == 'admin'))) {
        var button = getModuleDetailInstallButton(moduleName, td, buttonDiv);
        addEl(sdiv, button);
        addEl(td, sdiv);
        buttonDiv = sdiv;
        var sdiv = getEl('div');
        sdiv.id = 'installstatdiv_' + moduleName;
        sdiv.style.marginTop = '10px';
        sdiv.style.fontSize = '12px';
        if (installInfo[moduleName] != undefined) {
            sdiv.textContent = installInfo[moduleName]['msg'];
        }
        addEl(td, sdiv);
    } else if (currentTab == 'submit') {
        var sdiv = getEl('div');
        sdiv.id = 'installstatdiv_' + moduleName;
        sdiv.style.marginTop = '10px';
        sdiv.style.fontSize = '12px';
        if (installInfo[moduleName] != undefined) {
            sdiv.textContent = installInfo[moduleName]['msg'];
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
	$.get('/store/modules/'+moduleName+'/'+'latest'+'/readme').done(function(data){
        var protocol = window.location.protocol;
        if (protocol == 'http:') {
            mdDiv.innerHTML = data;
        } else if (protocol == 'https:') {
            mdDiv.innerHTML = data.replace(/http:/g, 'https:');
        }
        // output column description
        var d = getEl('div');
        d.id = 'moduledetail-output-column-div-' + currentTab;
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
        otbody.id = 'moduledetail-' + currentTab + '-output-tbody';
        addEl(otable, otbody);
        $.ajax({
            url: '/store/remotemoduleconfig', 
            data: {'module': moduleName},
            success: function (data) {
                var otbody = document.getElementById('moduledetail-' + currentTab + '-output-tbody');
                var outputColumnDiv = document.getElementById('moduledetail-output-column-div-' + currentTab);
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
        addEl(d, otable);
        addEl(mdDiv, d);
        addClassRecursive(mdDiv, 'moduledetaildiv-' + currentTab + '-elem');
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
    }
    addEl(d,span);
    addEl(infodiv,d);
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
    if (currentTab == 'store' && localModuleInfo[moduleName] != undefined) {
        var localVersion = localModuleInfo[moduleName].version;
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
    if (currentTab == 'store') {
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
    if (currentTab == 'store') {
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
    el.addEventListener('click', function (evt) {
        var pel = evt.target.parentElement;
        pel.parentElement.removeChild(pel);
    });
    addEl(div, el);
    addClassRecursive(div, 'moduledetaildiv-' + currentTab + '-elem');
    storeModuleDivClicked = true;
    return div;
}

function addClassRecursive (elem, className) {
    elem.classList.add(className);
    $(elem).children().each(
        function () {
            $(this).addClass(className);
            addClassRecursive(this, className);
        }
    );
}

function compareVersion (ver1, ver2) {
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

function getHighestVersionForRemoteModule (module) {
    var versions = remoteModuleInfo[module].versions;
    var highestVersion = '0.0.0';
    for (var i = 0; i < versions.length; i++) {
        var version = versions[i];
        var c = compareVersion(version, highestVersion);
        if (c > 0) {
            highestVersion = version;
        }
    }
    return highestVersion;
}

function getSizeText (size) {
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

function queueInstall (moduleName, version) {
    $.get('/store/queueinstall', {'module': moduleName, 'version': version}).done(
        function (response) {
            var keys = Object.keys(installInfo);
            if (keys.length == 0) {
                installInfo[moduleName] = {'msg': 'installing'};
            } else {
                installInfo[moduleName] = {'msg': 'queued'};
            }
            installQueue.push(moduleName);
            if (baseInstalled) {
                populateAllModulesDiv();
            }
        }
    );
}

function installModule (moduleName) {
	var version = remoteModuleInfo[moduleName]['latest_version'];
	$.ajax({
		type:'GET',
		url:'/store/install',
		data: {name:moduleName, version:version},
        success: function (response) {
            getLocal();
        }
	});
}

function uninstallModule(moduleName) {
    installInfo[moduleName] = {'msg': 'uninstalling'};
    populateAllModulesDiv();
	$.ajax({
        type:'GET',
        url:'/store/uninstall',
        data: {name: moduleName},
        complete: function (response) {
            delete installInfo[moduleName];
            moduleChange(response);
            populateAnnotators();
        }
	});
}

function moduleChange (data) {
	getLocal();
}

function setServerStatus (connected) {
    var overlay = document.getElementById('store-noconnect-div');
    if (! connected) {
        overlay.style.display = 'block';
    } else {
        overlay.style.display = 'none';
    }
}

function setModuleTileInstallButton (module) {
    $('div.moduletile[module=' + module + ']').each(function (i, div) {
        $(div).children('button').remove();
        var button = getModuleTileInstallButton(module);
        addEl(div, button);
        $(div).children('div.panelinstallprogressspan').text('');
    });
}

function unqueue (moduleName) {
    var idx = installQueue.indexOf(moduleName);
    if (idx >= 0) {
        installQueue.splice(idx, 1);
    }
}

function checkConnection(failures) {
	failures = failures !== undefined ? failures : 0;
    var host = window.location.host;
    if (failures>=3) {
        setServerStatus(false);
    }
    var protocol = window.location.protocol;
    var ws = null;
    if (protocol == 'http:') {
        ws = new WebSocket('ws://' + host + '/heartbeat');
    } else if (protocol == 'https:') {
        ws = new WebSocket('wss://' + host + '/heartbeat');
    }
    ws.onopen = function (evt) {
        setServerStatus(true);
        failures=0;
    }
    ws.onclose = function (evt) {
        failures += 1;
        var waitTime = 2000*failures;
        setTimeout(function() {
            checkConnection(failures);
        }, waitTime)
    }
    ws.onerror = function(evt) {
    }
    ws.onmessage = function (evt) {
    }
}

function connectWebSocket () {
    var host = window.location.host;
    var protocol = window.location.protocol;
    var ws = null;
    if (protocol == 'http:') {
        ws = new WebSocket('ws://' + host + '/store/connectwebsocket');
    } else if (protocol == 'https:') {
        ws = new WebSocket('wss://' + host + '/store/connectwebsocket');
    }
    ws.onopen = function (evt) {
    }
    ws.onclose = function (evt) {
        console.log('Re-establishing websocket');
        connectWebSocket(failures);
    }
    ws.onmessage = function (evt) {
        var data = JSON.parse(evt.data);
        var module = data['module'];
        var msg = data['msg'];
        var isbase = data['isbase'];
        if (installInfo[module] == undefined) {
            installInfo[module] = {};
        }
        installInfo[module]['msg'] = msg;
        var installstatdiv = null;
        if (baseToInstall.length > 0 || baseInstalled == false) {
            installstatdiv = document.getElementById('store-systemmodule-msg-div');
        } else {
            var divModuleName = module;
            installstatdiv = document.getElementById('installstatdiv_' + divModuleName);
        }
        if (installstatdiv != null) {
            installstatdiv.textContent = msg;
        }
        var sdivs = $('div.moduletile[module=' + module + '] .panelinstallprogressspan');
        for (var i1 = 0; i1 < sdivs.length; i1++) {
            var sdiv = sdivs[i1];
            sdiv.style.color = 'black';
            sdiv.textContent = msg;
        }
        if (msg.startsWith('Finished installation of')) {
            delete installInfo[module];
            //installQueue = installQueue.filter(e => e != module);
            unqueue(module);
            moduleChange(null);
            populateAnnotators();
            if (installQueue.length > 0) {
                var module = installQueue.shift();
                installInfo[module] = {'msg': 'installing'};
            }
        } else if (msg.startsWith('Aborted ')) {
            delete installInfo[module];
            unqueue(module);
            setModuleTileInstallButton (module);
        } else if (msg.startsWith('Unqueued')) {
            delete installInfo[module];
            unqueue(module);
            setModuleTileInstallButton (module);
        } else {
            var idx = uninstalledModules.indexOf(module);
            if (idx >= 0) {
                setModuleTileAbortButton(module);
                uninstalledModules.splice(idx, 1);
            }
        }
    }
}

function setModuleTileAbortButton (module) {
    $('div.moduletile[module=' + module + ']').each(function (i, div) {
        $(div).children('button').remove();
        var button = getModuleTileAbortButton(module);
        addEl(div, button);
    });
}

function getBaseModuleNames () {
    $.get('/store/getbasemodules').done(function (response) {
        baseModuleNames = response;
    });
}

function onStoreTagCheckboxChange () {
    updateFilter();
}

function showYesNoDialog (content, yescallback, noSpace, justOk) {
    var div = document.getElementById('yesnodialog');
    if (div != undefined) {
        $(div).remove();
    }
    var div = getEl('div');
    div.id = 'yesnodialog';
    content.id = 'yesnodialog-contentdiv'
    addEl(div, content);
    addEl(div, getEl('br'));
    var btnDiv = getEl('div');
    if (justOk) {
        btnDiv.className = 'buttondiv';
        var btn = getEl('button');
        btn.textContent = 'Ok';
        btn.addEventListener('click', function (evt) {
            if (yescallback == undefined || yescallback == null) {
                $('#yesnodialog').remove();
            } else {
                yescallback();
            }
        });
        addEl(btnDiv, btn);
    } else {
        btnDiv.className = 'buttondiv';
        var btn = getEl('button');
        btn.textContent = 'Yes';
        btn.addEventListener('click', function (evt) {
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
        btn.addEventListener('click', function (evt) {
            $('#yesnodialog').remove();
            yescallback(false);
        });
        addEl(btnDiv, btn);
    }
    addEl(div, btnDiv);
    addEl(document.body, div);
}

function onClickStoreInstallAllButton () {
    $.ajax({
        url: '/store/freemodulesspace', 
        async: true,
        success: function (response) {
            var freeSpace = response;
            var notInstalledModuleNames = getNotInstalledModuleNames();
            var div = getEl('div');
            var span = getEl('span');
            span.textContent = 'Modules to install are:';
            addEl(div, span);
            addEl(div, getEl('br'));
            addEl(div, getEl('br'));
            var totalSizeN = 0;
            for (var i = 0; i < notInstalledModuleNames.length; i++) {
                totalSizeN += remoteModuleInfo[notInstalledModuleNames[i]].size;
                var span = getEl('span');
                span.textContent = notInstalledModuleNames[i];
                span.style.fontWeight = 'bold';
                addEl(div, span);
                addEl(div, getEl('br'));
            }
            var noSpace = false;
            if (totalSizeN > freeSpace) {
                noSpace = true;
            }
            addEl(div, getEl('br'));
            totalSize = getSizeText(totalSizeN);
            var span = getEl('span');
            if (noSpace) {
                span.textContent = 'Total installation size is ';
                addEl(div, span);
                var span = getEl('span');
                span.textContent = totalSize;
                span.style.fontWeight = 'bold';
                addEl(div, span);
                addEl(div, getEl('br'));
                addEl(div, getEl('br'));
                var span = getEl('span');
                span.textContent = 'Not enough space on your modules disk!';
                //span.style.fontWeight = 'bold';
                span.style.color = 'red';
                addEl(div, span);
            } else {
                span.textContent = 'Total installation size is ';
                addEl(div, span);
                var span = getEl('span');
                span.textContent = totalSize;
                span.style.fontWeight = 'bold';
                addEl(div, span);
                addEl(div, getEl('br'));
                var span = getEl('span');
                span.textContent = 'Install them all?';
                addEl(div, span);
            }
            var yescallback = function (yn) {
                if (yn == true) {
                    for (var i = 0; i < notInstalledModuleNames.length; i++) {
                        queueInstall(notInstalledModuleNames[i]);
                    }
                }
            };
            showYesNoDialog(div, yescallback, noSpace);
        },
    });
}

function getSystemModulesToUpdate () {
    var modulesToUpdate = [];
    for (var i = 0; i < baseModuleNames.length; i++) {
        var moduleName = baseModuleNames[i];
        var module = origRemoteModuleInfo[moduleName];
        if (module['tags'].indexOf('newavailable') >= 0) {
            if (!updateConflicts.hasOwnProperty(moduleName)) {
                modulesToUpdate.push(moduleName);
            }
        }
    }
    return modulesToUpdate;
}

function getModulesToUpdate () {
    var modulesToUpdate = [];
    for (var moduleName in updates) {
        if (remoteModuleInfo[moduleName] != undefined) {
            if (remoteModuleInfo[moduleName]['tags'].indexOf('newavailable') >= 0) {
                if (!updateConflicts.hasOwnProperty(moduleName)) {
                    modulesToUpdate.push(moduleName);
                }
            }
        }
    }
    return modulesToUpdate;
}

function onClickSystemModuleUpdateButton () {
    var modulesToUpdate = getSystemModulesToUpdate();
    var div = getEl('div');
    var updateModuleNames = Object.keys(updates);
    var totalSizeN = 0;
    baseToInstall = [];
    for (var i = 0; i < updateModuleNames.length; i++) {
        var moduleName = updateModuleNames[i];
        var module = updates[moduleName];
        if (baseModuleNames.includes(moduleName)) {
            baseToInstall.push(moduleName);
            totalSizeN += module['size'];
        }
    }
    $.ajax({
        url: '/store/freemodulesspace',
        ajax: true,
        success: function (response) {
            var freeSpace = response;
            var noSpace = false;
            if (totalSizeN > freeSpace) {
                noSpace = true;
            }
            var totalSize = getSizeText(totalSizeN);
            var span = getEl('span');
            span.textContent = 'Total update size is ';
            addEl(div, span);
            var span = getEl('span');
            span.textContent = totalSize;
            span.style.fontWeight = 'bold';
            addEl(div, span);
            addEl(div, getEl('br'));
            addEl(div, getEl('br'));
            if (noSpace) {
                var span = getEl('span');
                span.textContent = 'Not enough space on your modules disk!';
                //span.style.fontWeight = 'bold';
                span.style.color = 'red';
                addEl(div, span);
            } else {
                var span = getEl('span');
                span.textContent = 'Update system modules?';
                addEl(div, span);
                var yescallback = function (yn) {
                    if (yn == true) {
                        startUpdatingSystemModules();
                    }
                };
            }
            showYesNoDialog(div, yescallback, noSpace);
        },
    });
}

function startUpdatingSystemModules () {
    document.getElementById('store-systemmodule-msg-div').textContent = '';
    showSystemModulePage();
    document.getElementById('store-systemmodule-update-div').style.display = 'block';
    for (var i = 0; i < baseToInstall.length; i++) {
        queueInstall(baseToInstall[i]);
    }
}

function onClickStoreUpdateAllButton () {
    var modulesToUpdate = getModulesToUpdate();
    var div = getEl('div');
    var span = getEl('span');
    span.textContent = 'Modules to update are:';
    addEl(div, span);
    addEl(div, getEl('br'));
    addEl(div, getEl('br'));
    var totalSizeN = 0;
    for (var i = 0; i < modulesToUpdate.length; i++) {
        totalSizeN += updates[modulesToUpdate[i]].size;
        var span = getEl('span');
        span.textContent = modulesToUpdate[i];
        span.style.fontWeight = 'bold';
        addEl(div, span);
        addEl(div, getEl('br'));
    }
    $.ajax({
        url: '/store/freemodulesspace',
        ajax: true,
        success: function (response) {
            var freeSpace = response;
            var noSpace = false;
            if (totalSizeN > freeSpace) {
                noSpace = true;
            }
            addEl(div, getEl('br'));
            var totalSize = getSizeText(totalSizeN);
            var span = getEl('span');
            span.textContent = 'Total update size is ';
            addEl(div, span);
            var span = getEl('span');
            span.textContent = totalSize;
            span.style.fontWeight = 'bold';
            addEl(div, span);
            addEl(div, getEl('br'));
                addEl(div, getEl('br'));
            if (noSpace) {
                var span = getEl('span');
                span.textContent = 'Not enough space on your modules disk!';
                //span.style.fontWeight = 'bold';
                span.style.color = 'red';
                addEl(div, span);
            } else {
                var span = getEl('span');
                span.textContent = 'Update them all?';
                addEl(div, span);
                var yescallback = function (yn) {
                    if (yn == true) {
                        announceStoreUpdatingAll();
                        for (var i = 0; i < modulesToUpdate.length; i++) {
                            queueInstall(modulesToUpdate[i]);
                        }
                    }
                };
            }
            showYesNoDialog(div, yescallback, noSpace);
        },
    });
}

function announceStoreUpdatingAll () {
    var span = document.getElementById('store-update-all-span');
    var button = document.getElementById('store-update-all-button');
    span.textContent = 'Updating all available modules...';
    button.style.display = 'none';
}

function announceStoreUpdateAllAvailable () {
    var span = document.getElementById('store-update-all-span');
    var button = document.getElementById('store-update-all-button');
    span.textContent = 'Updates to your installed modules are available!';
    button.style.display = 'inline';
}

function webstore_run () {
    document.addEventListener('click', function (evt) {
        if (evt.target.closest('moduledetaildiv_store') == null) {
            var div = document.getElementById('moduledetaildiv_store');
            if (div != null) {
                div.style.display = 'none';
            }
        }
    });
    connectWebSocket();
    getBaseModuleNames();
	getRemote();
}
