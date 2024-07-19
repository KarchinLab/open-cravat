'use strict';
import {
    getTn, addEl, getEl, PubSub, OC,
    emptyElement, getSizeText, removeElementFromArrayByValue, getTimestamp,
    addClassRecursive, compareVersion, prettyBytes
} from '../../submit/nocache/core.js';
import {
    getRemote, getLocal, populateAnnotators, makeModuleDetailDialog, addLogo
} from "../../submit/nocache/moduleinfo.js";

OC.currentDetailModule = null;
OC.remoteModuleInfo = {};
OC.origRemoteModuleInfo = null;
OC.localModuleInfo = {};
OC.updates = {};
OC.updateConflicts = null;
OC.filter = {};
OC.installQueue = [];
OC.installInfo = {};
OC.baseModuleNames = [];
OC.storeUrl = null;
OC.newModuleAvailable = false;
OC.baseModuleUpdateAvailable = false;
OC.storeFirstOpen = true;
OC.storeTileWidthStep = 470;
OC.storeTileHeight = 140
OC.modulesToIgnore = [
    'aggregator',
];
OC.storeLogos = {};
OC.moduleLists = {};
OC.baseToInstall = [];
OC.baseInstalled = false;
OC.defaultWidgetNames = [];
OC.uninstalledModules = [];
OC.moduleGroupMembers = {};
OC.currentPage = null;
OC.installedGroups = {};
OC.tagsCollected = [];
OC.tagDesc = {};
OC.numModulesInHomeSectionCol = 3
OC.numModulesInHomeSectionRow = 2
OC.numModulesInHomeSectionPage = 3
$.get('/store/getstoreurl').done(function(response) {
    OC.storeUrl = response;
});
if (!OC.mediator) {
    OC.mediator = new PubSub();
}

function onClickStoreHome() {
    $('.store-tag-checkbox').each(function() {
        this.checked = false;
    });
    showAllModulesDiv();
    updateFilter();
    showStoreHome();
}

function onClickStoreTagResetButton() {
    document.getElementById('store-namefilter').value = '';
    $('.store-tag-checkbox').each(function() {
        this.checked = false;
    });
    updateFilter();
    document.getElementById('store-tag-checkbox-home').checked = false;
    document.getElementById('store-tag-checkbox-viewall').checked = true;
}

function clickTab(value) {
    var tabs = document.getElementById('pageselect').children;
    for (var i = 0; i < tabs.length; i++) {
        var tab = tabs[i];
        if (tab.getAttribute('value') == value) {
            tab.click();
            return;
        }
    }
}

function hidePageselect() {
    document.getElementById('pageselect').style.display = 'none';
}

function showPageselect() {
    document.getElementById('pageselect').style.display = 'block';
}

function onClickInstallBaseComponents() {
    document.getElementById('store-systemmodule-msg-div').textContent = '';
    var btn = document.getElementById('store-systemmodule-install-button');
    btn.classList.add('disabled');
    installBaseComponents();
    document.getElementById('messagediv').style.display = 'none';
}

function showSystemModulePage() {
    document.getElementById('store-systemmodule-div').style.display = 'block';
    if (OC.systemReadyObj.ready == false) {
        document.getElementById('store-systemmodule-systemnotready-div').style.display = 'block';
        var span = document.getElementById('store-systemmodule-systemnotready-span');
        var span2 = document.getElementById('store-systemmodule-systemnotready-span2');
        span.textContent = OC.systemReadyObj['message'];
        if (OC.systemReadyObj['code'] == 1) {
            span2.textContent = 'Please use the settings menu at top right to set the correct modules directory.';
        }
    } else {
        if (OC.baseInstalled == false) {
            document.getElementById('store-systemmodule-missing-div').style.display = 'block';
        } else {
            document.getElementById('store-systemmodule-missing-div').style.display = 'none';
        }
        document.getElementById('store-systemmodule-update-div').style.display = 'none';
        if (OC.baseToInstall.length == 0) {
            document.getElementById('store-systemmodule-install-button').disabled = true;
        }
    }
}

function hideSystemModulePage() {
    document.getElementById('store-systemmodule-div').style.display = 'none';
}

function complementRemoteWithLocal() {
    var localModuleNames = Object.keys(OC.localModuleInfo);
    for (var i = 0; i < localModuleNames.length; i++) {
        var localModuleName = localModuleNames[i];
        if (localModuleName == 'example_annotator') {
            continue;
        }
        var localModule = OC.localModuleInfo[localModuleName];
        var remoteModule = OC.remoteModuleInfo[localModuleName];
        var check2 = localModule.conf.uselocalonstore;
        var check3 = localModule.conf['private'];
        if (check2 == true && check3 != true) {
            var xhr = new XMLHttpRequest();
            xhr.open('GET', '/store/localasremote?module=' + localModuleName, false);
            xhr.onload = function(e) {
                var moduleInfo = JSON.parse(xhr.responseText);
                if (moduleInfo.private == true) {
                    return;
                }
                OC.remoteModuleInfo[localModuleName] = moduleInfo;
            };
            xhr.onerror = function(e) {
                console.error(xhr.statusText);
            };
            xhr.send();
        }
    }
}

function setupJobsTab() {
    complementRemoteWithLocal();
    OC.mediator.publish('setupJobs');
}



function setBaseInstalled() {
    OC.baseInstalled = true;
    var moduleNamesInInstallQueue = Object.keys(OC.installInfo);
    OC.baseToInstall = [];
    for (var i = 0; i < OC.baseModuleNames.length; i++) {
        var baseModuleName = OC.baseModuleNames[i];
        if (!(baseModuleName in OC.localModuleInfo)) {
            OC.baseInstalled = false;
            if (moduleNamesInInstallQueue.indexOf(baseModuleName) == -1) {
                OC.baseToInstall.push(baseModuleName);
            }
        }
    }
    var div = document.getElementById('remotemodulepanels');
    if (div == null) {
        return;
    }
    if (OC.origRemoteModuleInfo == null) {
        OC.origRemoteModuleInfo = JSON.parse(JSON.stringify(OC.remoteModuleInfo));
    }
}

function populateStorePages() {
    if (OC.baseInstalled) {
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
                makeModuleDetailDialog(OC.currentDetailModule, null, null);
            }
        }
        populateStoreHome();
        populateAllModulesDiv();
        var mg = document.getElementById('store-modulegroup-div').getAttribute('modulegroup');
        if (mg != undefined && mg != '') {
            populateModuleGroupDiv(mg);
        }
        if (OC.storeFirstOpen) {
            showStoreHome();
        }
        OC.storeFirstOpen = false;
    } else {
        hidePageselect();
        showSystemModulePage();
    }
}



function showOrHideSystemModuleUpdateButton() {
    if (OC.servermode == false || (OC.logged == true && OC.username == 'admin')) {
        OC.baseModuleUpdateAvailable = false;
        var moduleNames = Object.keys(OC.updates);
        for (var i = 0; i < moduleNames.length; i++) {
            if (OC.baseModuleNames.includes(moduleNames[i])) {
                OC.baseModuleUpdateAvailable = true;
                break;
            }
        }
        var btn = document.getElementById('store-systemmoduleupdate-announce-div');
        if (OC.baseModuleUpdateAvailable) {
            btn.style.display = 'inline-block';
        } else {
            btn.style.display = 'none';
        }
    }
}

function showOrHideUpdateAllButton() {
    var d = document.getElementById('store-update-all-div');
    if (OC.newModuleAvailable && (OC.servermode == false || (OC.logged == true && OC.username == 'admin'))) {
        var modulesInInstallQueue = Object.keys(OC.installInfo);
        d.style.display = 'block';
        announceStoreUpdateAllAvailable();
    } else {
        d.style.display = 'none';
        disableUpdateAvailable()
    }
}

function showStoreHome() {
    document.getElementById('store-tag-checkbox-home').checked = true;
    document.getElementById('store-tag-checkbox-viewall').checked = false;
    document.getElementById('store-home-div').style.display = 'block';
    document.getElementById('store-allmodule-div').style.display = 'none';
    document.getElementById('store-modulegroup-div').style.display = 'none';
}

function hideStoreHome() {
    document.getElementById('store-tag-checkbox-home').checked = false;
    document.getElementById('store-home-div').style.display = 'none';
    document.getElementById('store-allmodule-div').style.display = 'block';
    document.getElementById('store-modulegroup-div').style.display = 'none';
}

function showAllModulesDiv() {
    document.getElementById('store-tag-checkbox-home').checked = false;
    document.getElementById('store-home-div').style.display = 'none';
    document.getElementById('store-allmodule-div').style.display = 'block';
    document.getElementById('store-modulegroup-div').style.display = 'none';
}

function showStoreModuleGroup() {
    document.getElementById('store-tag-checkbox-home').checked = false;
    document.getElementById('store-home-div').style.display = 'none';
    document.getElementById('store-allmodule-div').style.display = 'none';
    document.getElementById('store-modulegroup-div').style.display = 'block';
}

function hideStoreModuleGroup() {
    document.getElementById('store-tag-checkbox-home').checked = false;
    document.getElementById('store-home-div').style.display = 'none';
    document.getElementById('store-allmodule-div').style.display = 'block';
    document.getElementById('store-modulegroup-div').style.display = 'none';
}

function onClickModuleGroupDivBackArrow(evt) {
    if (OC.currentPage == 'store-home-div') {
        showStoreHome();
    } else if (OC.currentPage == 'store-allmodule-div') {
        showAllModulesDiv();
    } else if (OC.currentPage == 'store-modulegroup-div') {
        showStoreModuleGroup();
    }
}

function getMostDownloadedModuleNames() {
    var moduleNames = Object.keys(OC.remoteModuleInfo);
    for (var i = 0; i < moduleNames.length; i++) {
        for (var j = i + 1; j < moduleNames.length - 1; j++) {
            var d1 = OC.remoteModuleInfo[moduleNames[i]].downloads;
            var d2 = OC.remoteModuleInfo[moduleNames[j]].downloads;
            if (d1 < d2) {
                var tmp = moduleNames[i];
                moduleNames[i] = moduleNames[j];
                moduleNames[j] = tmp;
            }
        }
    }
    var top10ModuleNames = [];
    var count = 0;
    var numModulesInHomeSection = OC.numModulesInHomeSectionRow * OC.numModulesInHomeSectionCol * OC.numModulesInHomeSectionPage
    for (var i = 0; i < moduleNames.length; i++) {
        var moduleName = moduleNames[i];
        if (moduleName == 'base') {
            continue;
        }
        if (OC.baseModuleNames.indexOf(moduleName) >= 0) {
            continue;
        }
        if (OC.remoteModuleInfo[moduleName].hidden == true) {
            continue;
        }
        if (OC.remoteModuleInfo[moduleName].type == 'webviewerwidget' && OC.defaultWidgetNames.includes(moduleName)) {
            continue;
        }
        if (OC.remoteModuleInfo[moduleName].type == 'group') {
            continue
        }
        if (OC.baseModuleNames.indexOf(moduleName) >= 0) {
            continue
        }
        top10ModuleNames.push(moduleName);
        count++;
        if (count == numModulesInHomeSection) {
            break;
        }
    }
    return top10ModuleNames;
}

function getNewestModuleNames() {
    var moduleNames = Object.keys(OC.remoteModuleInfo);
    for (var i = 0; i < moduleNames.length; i++) {
        for (var j = i + 1; j < moduleNames.length - 1; j++) {
            var n1 = moduleNames[i];
            var n2 = moduleNames[j];
            var m1 = OC.remoteModuleInfo[n1];
            var m2 = OC.remoteModuleInfo[n2];
            var d1 = new Date(m1.publish_time);
            var d2 = new Date(m2.publish_time);
            if (d1 < d2) {
                var tmp = moduleNames[i];
                moduleNames[i] = moduleNames[j];
                moduleNames[j] = tmp;
            }
        }
    }
    var top10ModuleNames = [];
    var count = 0;
    var numModulesInHomeSection = OC.numModulesInHomeSectionRow * OC.numModulesInHomeSectionCol * OC.numModulesInHomeSectionPage
    for (var i = 0; i < moduleNames.length; i++) {
        var moduleName = moduleNames[i];
        if (moduleName == 'base') {
            continue;
        }
        if (OC.baseModuleNames.indexOf(moduleName) >= 0) {
            continue;
        }
        var m = OC.remoteModuleInfo[moduleName];
        if (m.hidden == true) {
            continue;
        }
        if (m.type == 'webviewerwidget' && OC.defaultWidgetNames.includes(moduleName)) {
            continue;
        }
        if (m.groups.length > 0) {
            continue;
        }
        top10ModuleNames.push(moduleName);
        count++;
        if (count == numModulesInHomeSection) {
            break;
        }
    }
    return top10ModuleNames;
}

function getHomeCarouselContent (modules, type) {
    var sdiv = getEl('div');
    sdiv.style.width = (Math.ceil(modules.length / OC.numModulesInHomeSectionRow) * OC.storeTileWidthStep) + 'px'
    sdiv.style.height = OC.numModulesInHomeSectionRow * OC.storeTileHeight
    for (var i = 0; i < modules.length; i = i + OC.numModulesInHomeSectionRow) {
        var ssdiv = getEl('div')
        ssdiv.classList.add('home-tile-group')
        for (var j = 0; j < OC.numModulesInHomeSectionRow; j++) {
            var n = i + j
            if (n < modules.length) {
                var panel = getRemoteModulePanel(modules[n], type, n);
                addEl(ssdiv, panel);
            }
        }
        addEl(sdiv, ssdiv)
    }
    return sdiv
}

function populateStoreHome() {
    // Most Downloaded
    var div = document.getElementById('store-home-featureddiv');
    $(div).empty();
    var featuredModules = getMostDownloadedModuleNames();
    OC.moduleLists['download'] = featuredModules;
    var sdiv = getHomeCarouselContent(featuredModules, 'download')
    addEl(div, sdiv);
    // Newest
    var div = document.getElementById('store-home-newestdiv');
    $(div).empty();
    var newestModules = getNewestModuleNames();
    OC.moduleLists['newest'] = newestModules;
    var sdiv = getHomeCarouselContent(newestModules, 'newest')
    addEl(div, sdiv);
    // Cancer 
    var div = document.getElementById('store-home-cancerdiv');
    $(div).empty();
    var sdiv = getEl('div');
    var cancerModules = [];
    var remoteModuleNames = Object.keys(OC.remoteModuleInfo);
    for (var i = 0; i < remoteModuleNames.length; i++) {
        var remoteModuleName = remoteModuleNames[i];
        var remoteModule = OC.remoteModuleInfo[remoteModuleName];
        if (remoteModule['groups'].length > 0) {
            continue;
        }
        if (remoteModule['tags'].includes('cancer')) {
            cancerModules.push(remoteModuleName);
        }
    }
    OC.moduleLists['cancer'] = cancerModules;
    var sdiv = getHomeCarouselContent(cancerModules, 'cancer')
    addEl(div, sdiv);
    // Clinical Relevance
    var div = document.getElementById('store-home-clinicaldiv');
    $(div).empty();
    var sdiv = getEl('div');
    var clinicalModules = [];
    var remoteModuleNames = Object.keys(OC.remoteModuleInfo);
    for (var i = 0; i < remoteModuleNames.length; i++) {
        var remoteModuleName = remoteModuleNames[i];
        var remoteModule = OC.remoteModuleInfo[remoteModuleName];
        if (remoteModule['groups'].length > 0) {
            continue;
        }
        if (remoteModule['tags'].includes('clinical relevance')) {
            clinicalModules.push(remoteModuleName);
        }
    }
    OC.moduleLists['clinical'] = clinicalModules;
    var sdiv = getHomeCarouselContent(clinicalModules, 'clinical')
    addEl(div, sdiv);
}

function getCarouselScrollStep (d) {
    var dw = d.offsetWidth;
    var sw = null
    if (dw >= OC.storeTileWidthStep * 3) {
        sw = OC.storeTileWidthStep * 3
    } else if (dw >= OC.storeTileWidthStep * 2) {
        sw = OC.storeTileWidthStep * 2
    } else {
        sw = OC.storeTileWidthStep
    }
    return sw
}

function onClickStoreHomeLeftArrow(el) {
    let target = el.target;
    var d = target.nextElementSibling;
    var dw = d.offsetWidth;
    var sw = getCarouselScrollStep(d)
    var s = d.scrollLeft;
    s -= Math.floor(dw / sw) * sw;
    $(d).animate({
        scrollLeft: s
    }, 100);
}

function onClickStoreHomeRightArrow(el) {
    let target = el.target;
    var d = target.previousElementSibling;
    var dw = d.offsetWidth;
    var sw = getCarouselScrollStep(d)
    var s = d.scrollLeft;
    s += Math.floor(dw / sw) * sw;
    $(d).animate({
        scrollLeft: s
    }, 100);
}

function trimRemote() {
    var remoteModuleNames = Object.keys(OC.remoteModuleInfo);
    OC.defaultWidgetNames = [];
    for (var i = 0; i < remoteModuleNames.length; i++) {
        var remoteModuleName = remoteModuleNames[i];
        var remoteModule = OC.remoteModuleInfo[remoteModuleName];
        if (remoteModule.type == 'annotator') {
            OC.defaultWidgetNames.push('wg' + remoteModuleName);
        }
    }
    for (var i = 0; i < remoteModuleNames.length; i++) {
        var remoteModuleName = remoteModuleNames[i];
        var remoteModule = OC.remoteModuleInfo[remoteModuleName];
        if (remoteModule.tags == null) {
            remoteModule.tags = [];
        }
        if (OC.modulesToIgnore.includes(remoteModuleName) && remoteModule.tags.includes('newavailable') == false) {
            delete OC.remoteModuleInfo[remoteModuleName];
            continue;
        }
        if (OC.baseModuleNames.includes(remoteModuleName)) {
            delete OC.remoteModuleInfo[remoteModuleName];
            if (remoteModule.tags.includes('newavailable')) {
                OC.baseModuleUpdateAvailable = true;
            }
            continue;
        }
        var remoteModule = OC.remoteModuleInfo[remoteModuleName];
        if (remoteModule.type == 'webviewerwidget' &&
            OC.defaultWidgetNames.includes(remoteModuleName) && remoteModule.tags.includes('newavailable') == false) {
            delete OC.remoteModuleInfo[remoteModuleName];
            continue;
        }
        if (remoteModule.hidden == true && remoteModule.tags.includes('newavailable') == false) {
            delete OC.remoteModuleInfo[remoteModuleName];
            continue;
        }
    }
}


function getNotInstalledModuleNames() {
    var notInstalledModuleNames = [];
    for (var module in OC.remoteModuleInfo) {
        var tags = OC.remoteModuleInfo[module].tags;
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

function populateStoreTagPanel() {
    OC.tagsCollected = [];
    for (var module in OC.remoteModuleInfo) {
        var tags = OC.remoteModuleInfo[module].tags;
        for (var i = 0; i < tags.length; i++) {
            var tag = tags[i];
            if (tag == 'gene-level' || tag == 'variant-level') {}
            if (OC.tagsCollected.indexOf(tag) == -1) {
                OC.tagsCollected.push(tag);
            }
        }
    }

    removeElementFromArrayByValue(OC.tagsCollected, 'frontpage');
    removeElementFromArrayByValue(OC.tagsCollected, 'viewall');
    removeElementFromArrayByValue(OC.tagsCollected, 'newavailable');
    OC.tagsCollected.sort();
    var div = document.getElementById('store-tag-custom-div');
    $(div).empty();
    for (var i = 0; i < OC.tagsCollected.length; i++) {
        var tag = OC.tagsCollected[i];
        var label = getEl('label');
        label.className = 'checkbox-store-container';
        label.textContent = tag;
        if (OC.tagDesc[tag] != undefined) {
            label.title = OC.tagDesc[tag];
        }
        var input = getEl('input');
        input.type = 'checkbox';
        input.value = tag;
        input.className = 'store-tag-checkbox';
        input.addEventListener('click', function(evt) {
            onStoreTagCheckboxChange();
        });
        var span = getEl('span');
        span.className = 'checkmark-store';
        addEl(label, input);
        addEl(label, span);
        addEl(div, label);
    }
}

function installBaseComponents() {
    for (var i = 0; i < OC.baseModuleNames.length; i++) {
        var module = OC.baseModuleNames[i];
        if (OC.localModuleInfo[module] == undefined || OC.localModuleInfo[module]['exists'] == false) {
            queueInstall(module);
        }
    }
}

function updateFilter() {
    var nameinput = document.getElementById('store-namefilter');
    var nameStr = nameinput.value;
    OC.filter = {};
    var filterHasValue = false;
    // Name filter
    if (nameStr != '') {
        OC.filter['name'] = [nameStr];
        filterHasValue = true;
    }
    // Tag filter
    var checkboxes = $('.store-tag-checkbox:checked');
    var tags = [];
    for (var i = 0; i < checkboxes.length; i++) {
        tags.push(checkboxes[i].value);
        filterHasValue = true;
    }
    if (tags.length > 0) {
        OC.filter['tags'] = tags;
    }
    populateAllModulesDiv();
    showAllModulesDiv();
    if (filterHasValue) {
        document.getElementById('store-tag-checkbox-viewall').checked = false;
    } else {
        document.getElementById('store-tag-checkbox-viewall').checked = true;
    }
}

function onClickModuleTileAbortButton(evt) {
    var moduleName = evt.target.getAttribute('module');
    $.ajax({
        url: '/store/killinstall',
        data: {
            'module': moduleName
        },
        ajax: true,
        success: function(response) {}
    });
}

function onClickModuleInstallButton(evt) {
    const button = evt.target;
    const moduleName = button.getAttribute('module');
    const doInstall = () => {
        queueInstall(moduleName);
        const storeDetailDiv = document.querySelector('#moduledetaildiv_store')
        if (storeDetailDiv !== null) storeDetailDiv.style.display = 'none';
        if (OC.installQueue.length == 0) {
            setModuleTileAbortButton(moduleName);
        } else {
            setModuleTileUnqueueButton(moduleName);
        }
        writeInstallationMsg(getTimestamp() + " Installing " + moduleName)
    }
    const installConfirmLimit = 5*1000**3;
    const preflightRequests = Promise.all([
        fetch('/store/freemodulesspace'),
        fetch('/store/moduledependencies?'+new URLSearchParams([
            ['module', moduleName]
        ]))
    ])
    preflightRequests.then(resps=>Promise.all(resps.map(r=>r.json())))
    .then(values=>{
        const [freeSpace, deps] = values;
        const neededSpace = Object.keys(deps).reduce(
            (a, depName) => {
                if (OC.remoteModuleInfo.hasOwnProperty(depName)) {
                    return a + OC.remoteModuleInfo[depName].size;
                } else {
                    return a;
                }
            },
            OC.remoteModuleInfo[moduleName].size
        );
        const moduleSizeSpan = (moduleName, moduleSize) => {
            return addEl(getEl('span'), getTn(`${moduleName}: ${prettyBytes(moduleSize)}`))
        };
        const noSpace = neededSpace > freeSpace;
        const aboveConfirmSize = neededSpace > installConfirmLimit
        if (noSpace || aboveConfirmSize) {
            const mdiv = getEl('div');
            var topSpan;
            var botSpan;
            if (noSpace) {
                topSpan = addEl(getEl('span'), getTn(
                    `Not enough disk space. ${prettyBytes(neededSpace)} required, ${prettyBytes(freeSpace)} available.`
                ));
                botSpan = addEl(getEl('span'), getTn(`Free ${prettyBytes(neededSpace-freeSpace)} install.`));
            } else {
                topSpan = addEl(getEl('span'), getTn(
                    `Installation requires ${prettyBytes(neededSpace)}.`
                ));
                botSpan = addEl(getEl('span'), getTn('Install?'));
            }
            addEl(mdiv, topSpan);
            if (Object.keys(deps).length > 0) {
                addEl(mdiv, getEl('br'));
                addEl(mdiv, getEl('br'));
                addEl(mdiv, addEl(getEl('span'), getTn('Installing:')));
                addEl(mdiv, getEl('br'));
                addEl(mdiv, moduleSizeSpan(moduleName, OC.remoteModuleInfo[moduleName].size));
                for (let depName in deps) {
                    if (OC.remoteModuleInfo.hasOwnProperty(depName)) {
                        addEl(mdiv, getEl('br'));
                        addEl(mdiv, moduleSizeSpan(depName, OC.remoteModuleInfo[depName].size));
                    }
                }
            }
            addEl(mdiv, getEl('br'));
            addEl(mdiv, getEl('br'));
            addEl(mdiv, botSpan);
            addEl(mdiv, getEl('br'));
            OC.mediator.publish('showyesnodialog', mdiv, userConfirm=>{
                if (userConfirm) {
                    doInstall();
                }
            }, noSpace, noSpace);
        } else {
            doInstall();
        }
    })
}

function setModuleTileUnqueueButton(moduleName) {
    $('div.moduletile[module=' + moduleName + ']').each(function(i, div) {
        $(div).children('button').remove();
        var button = getModuleTileUnqueueButton(moduleName);
        addEl(div, button);
    });
}

function onClickModuleTileUnqueueButton(evt) {
    var moduleName = evt.target.getAttribute('module');
    $.ajax({
        url: '/store/unqueue',
        data: {
            'module': moduleName
        },
        ajax: true,
        success: function(response) {},
    });
}

function getModuleTileUnqueueButton(moduleName) {
    var button = getEl('button');
    button.className = 'modulepanel-unqueueinstall-button';
    button.textContent = 'Cancel download';
    button.setAttribute('module', moduleName);
    button.addEventListener('click', onClickModuleTileUnqueueButton);
    return button;
}

function onClickModuleTileUpdateButton(evt) {
    var button = evt.target;
    var moduleName = button.getAttribute('module');
    var installSize = OC.updates[moduleName].size;
    $.ajax({
        url: '/store/freemodulesspace',
        ajax: true,
        success: function(response) {
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
                OC.mediator.publish('showyesnodialog', mdiv, null, noSpace, justOk);
                return;
            } else {
                queueInstall(moduleName, OC.updates[moduleName].version);
                if (OC.installQueue.length == 0) {
                    setModuleTileAbortButton(moduleName);
                } else {
                    setModuleTileUnqueueButton(moduleName);
                }
            }
        },
    });
}

function getModuleTileUpdateButton(moduleName) {
    var button = getEl('button');
    button.classList.add('butn');
    button.classList.add('modulepanel-update-button');
    button.textContent = 'UPDATE';
    button.setAttribute('module', moduleName);
    if (OC.updateConflicts.hasOwnProperty(moduleName)) {
        button.setAttribute('disabled', 'true');
        var blockList = [];
        for (blockName in OC.updateConflicts[moduleName]) {
            blockList.push(blockName);
        }
        blockString = blockList.join(', ');
        var titleText = 'Update blocked by: ' + blockString + '. Uninstall blocking modules to update.';
        button.setAttribute('title', titleText);
    }
    button.addEventListener('click', onClickModuleTileUpdateButton);
    return button;
}

function getModuleTileUninstallButton(moduleName) {
    var button = getEl('button');
    button.classList.add('butn');
    button.classList.add('modulepanel-uninstall-button');
    button.textContent = 'UNINSTALL';
    button.setAttribute('module', moduleName);
    button.addEventListener('click', function(evt) {
        var moduleName = evt.target.getAttribute('module');
        uninstallModule(moduleName);
    });
    return button;
}

function getModuleTileInstallButton(moduleName) {
    var div = getEl('div');
    div.classList.add('modulepanel-install-button-div');
    var button = getEl('button');
    button.classList.add('butn');
    button.classList.add('modulepanel-install-button');
    button.textContent = '\xa0INSTALL';
    button.setAttribute('module', moduleName);
    button.addEventListener('click', onClickModuleInstallButton);
    addEl(div, button);
    return div;
}

function getModuleTileAbortButton(moduleName) {
    var button = getEl('button');
    button.classList.add('butn');
    button.classList.add('modulepanel-stopinstall-button');
    button.textContent = 'Cancel download';
    button.setAttribute('module', moduleName);
    button.removeEventListener('click', onClickModuleInstallButton);
    button.addEventListener('click', onClickModuleTileAbortButton);
    return button;
}

function populateModuleGroupDiv(moduleGroupName) {
    document.getElementById('store-modulegroup-title-span').textContent = OC.remoteModuleInfo[moduleGroupName]['title'];
    var div = document.getElementById('store-modulegroup-content-div');
    emptyElement(div);
    div.parentElement.setAttribute('modulegroup', moduleGroupName);
    var remoteModuleNames = OC.moduleGroupMembers[moduleGroupName];
    if (remoteModuleNames == undefined) {
        var panel = getEl('div');
        panel.classList.add('no-group-member-msg-div');
        panel.textContent = 'No module in this group';
        addEl(div, panel);
    } else {
        OC.moduleLists['modulegroup'] = remoteModuleNames;
        for (var i = 0; i < remoteModuleNames.length; i++) {
            var remoteModuleName = remoteModuleNames[i];
            var remoteModule = OC.remoteModuleInfo[remoteModuleName];
            if (remoteModule == undefined) {
                continue;
            }
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

function saveCurrentPage() {
    var divIds = ['store-home-div', 'store-allmodule-div', 'store-modulegroup-div'];
    for (var i = 0; i < divIds.length; i++) {
        var divId = divIds[i];
        if (document.getElementById(divId).style.display != 'none') {
            OC.currentPage = divId;
            break;
        }
    }
}

function getRemoteModuleGroupPanel(moduleName, moduleListName, moduleListPos) {
    var moduleInfo = OC.remoteModuleInfo[moduleName];
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
    sdiv.onclick = function(evt) {
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
        img.onclick = function(evt) {
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
        if (moduleInfo.type == 'group') {
            sdiv.className = 'moduletile-group-typediv';
        } else {
            sdiv.className = 'moduletile-typediv';
        }
        sdiv.textContent = t;
        addEl(div, sdiv);
    }
    var members = OC.moduleGroupMembers[moduleName];
    var updateAvail = false;
    if (members != undefined) {
        for (var i = 0; i < members.length; i++) {
            var member = members[i];
            if (OC.remoteModuleInfo[member] == undefined) {
                continue;
            }
            if (OC.remoteModuleInfo[member].tags.indexOf('newavailable') != -1) {
                updateAvail = true;
                break;
            }
        }
    }
    if (updateAvail && (OC.servermode == false || (OC.logged == true && OC.username == 'admin'))) {
        var span = getEl('span');
        span.className = 'moduletile-group-updateavailable-span';
        span.textContent = 'Update available';
        addEl(div, span);
    }
    return div
}

function makeModuleDescUrlTitle(moduleName, text) {
    var moduleInfo = OC.remoteModuleInfo[moduleName];
    var text = moduleInfo['description']
    var div = getEl('div')
    var el = getEl('div')
    if (text != undefined) {
        el.textContent = text
    }
    el.classList.add('modulepanel-description-div')
    addEl(div, el)
    var annotators = OC.remoteModuleInfo[moduleName]['annotators']
    if (annotators == undefined) {
        annotators = moduleName
    }
    return div
}

function getRemoteModulePanel(moduleName, moduleListName, moduleListPos) {
    var moduleInfo = OC.remoteModuleInfo[moduleName];
    var titleEl = makeModuleDescUrlTitle(moduleName, moduleName)
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
    sdiv.onclick = function(evt) {
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
        img.onclick = function(evt) {
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
    var ssdiv = getEl('div');
    var titleEl = makeModuleDescUrlTitle(moduleName, moduleName)
    addEl(ssdiv, titleEl)
    addEl(sdiv, ssdiv);
    span = getEl('span');
    var datasource = moduleInfo['datasource'];
    if (moduleInfo.type != null && datasource != null && moduleInfo.type != 'annotator' && moduleInfo.type != 'group') {
        span.className = 'modulepanel-datasource-span-other';
    } else {
        span.className = 'modulepanel-datasource-span';
    }
    if (datasource == null) {
        datasource = '';
    }
    span.textContent = datasource;
    span.title = 'Data source version';
    addEl(div, span)
    addEl(div, sdiv);
    addEl(div, getEl('br'));
    var installStatus = '';
    var btnAddedFlag = false;
    if (OC.installInfo[moduleName] != undefined) {
        var msg = OC.installInfo[moduleName]['msg'];
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
        if (OC.localModuleInfo[moduleName] != undefined && OC.localModuleInfo[moduleName]['exists']) {
            installStatus = 'Installed';
        } else {
            installStatus = '';
        }
    }
    var progSpan = getEl('div');
    progSpan.id = 'panelinstallprogress_' + moduleName;
    progSpan.className = 'panelinstallprogressspan';
    if (OC.installInfo[moduleName] != undefined && installStatus == 'Installing...') {
        progSpan.textContent = OC.installInfo[moduleName]['msg'];
    }
    addEl(div, progSpan);
    var span = getEl('div');
    span.id = 'panelinstallstatus_' + moduleName;
    addEl(div, span);
    if (OC.servermode == false || (OC.logged == true && OC.username == 'admin')) {
        if (installStatus == 'Queued') {
            var button = getModuleTileUnqueueButton(moduleName);
            addEl(div, button);
        } else if (installStatus == 'Installing...') {
            var button = getModuleTileAbortButton(moduleName);
            addEl(div, button);
        } else if (installStatus == 'Installed') {
            if (OC.remoteModuleInfo[moduleName].tags.indexOf('newavailable') >= 0) {
                var button = getModuleTileUpdateButton(moduleName);
                addEl(div, button);
            } else {
                var button = getModuleTileUninstallButton(moduleName);
                addEl(div, button);
            }
        } else {
            var tags = OC.remoteModuleInfo[moduleName].tags;
            if (tags.indexOf('installed') >= 0) {
                var button = getModuleTileUninstallButton(moduleName);
                addEl(div, button);
            } else {
                var button = getModuleTileInstallButton(moduleName);
                addEl(div, button);
                OC.uninstalledModules.push(moduleName);
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
        if (moduleInfo.type == 'group') {
            sdiv.className = 'moduletile-group-typediv';
        } else {
            sdiv.className = 'moduletile-typediv';
        }
        sdiv.textContent = t;
        addEl(div, sdiv);
    }
    return div
}

function getFilteredRemoteModules() {
    var filteredRemoteModules = {};
    var remoteModuleNames = Object.keys(OC.remoteModuleInfo);
    var localModuleNames = Object.keys(OC.localModuleInfo);
    var hasFilter = Object.keys(OC.filter).length > 0;
    for (var i = 0; i < remoteModuleNames.length; i++) {
        var remoteModuleName = remoteModuleNames[i];
        var remoteModuleNameLower = remoteModuleName.toLowerCase();
        var remoteModule = OC.remoteModuleInfo[remoteModuleName];
        var newCheck = document.getElementById('store-tag-checkbox-newavailable').checked;
        if (remoteModule['groups'].length > 0) {
            var pass = false;
            if (OC.currentPage == 'storediv-modulegroup-div') {
                pass = true;
            } else if (remoteModule['tags'].indexOf('newavailable') != -1 && newCheck == true) {
                pass = true;
            } else if (hasFilter && newCheck == true) {
                pass = true;
            }
            if (pass == false) {
                continue;
            }
        } else {}
        if (hasFilter) {
            var typeYes = false;
            var nameYes = false;
            var tagYes = false;
            typeYes = true;
            if (OC.filter['name'] != undefined && OC.filter['name'] != '') {
                for (var j = 0; j < OC.filter['name'].length; j++) {
                    var queryStr = OC.filter['name'][j].toLowerCase();
                    var descStr = remoteModule['description'];
                    if (remoteModule['title'].toLowerCase().includes(queryStr) || (descStr != undefined && descStr.toLowerCase().includes(queryStr))) {
                        nameYes = true;
                        break;
                    }
                }
            } else {
                nameYes = true;
            }
            if (OC.filter['tags'] != undefined && OC.filter['tags'].length > 0) {
                tagYes = false;
                for (var j = 0; j < OC.filter['tags'].length; j++) {
                    if (remoteModule['tags'].indexOf(OC.filter['tags'][j]) >= 0) {
                        tagYes = true;
                        break;
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

function getSortedFilteredRemoteModuleNames() {
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

function populateAllModulesDiv(group) {
    var div = document.getElementById('remotemodulepanels');
    emptyElement(div);
    var remoteModuleNames = getSortedFilteredRemoteModuleNames();
    OC.moduleLists['all'] = remoteModuleNames;
    for (var i = 0; i < remoteModuleNames.length; i++) {
        var remoteModuleName = remoteModuleNames[i];
        var remoteModule = OC.remoteModuleInfo[remoteModuleName];
        if (group == 'basetoinstall') {
            if (OC.baseModuleNames.indexOf(remoteModuleName) == -1) {
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

function onClickProgressDivCloseIcon() {
    var progdiv = document.querySelector('#installationprogressmsgdiv')
    var chatdiv = document.querySelector('#chaticondiv')
    chatdiv.classList.remove('hide')
    progdiv.classList.remove('show')
}

function toggleChatBox() {
    var progdiv = document.querySelector('#installationprogressmsgdiv')
    var chatdiv = document.querySelector('#chaticondiv')
    if (chatdiv.classList.contains('hide')) {
        chatdiv.classList.remove('hide')
        progdiv.classList.remove('show')
    } else {
        chatdiv.classList.add('hide')
        chatdiv.classList.remove('new')
        progdiv.classList.add('show')
    }
}

function onClicModuleDetailAbortButton(evt) {
    var moduleName = evt.target.getAttribute('module');
    $.ajax({
        url: '/store/killinstall',
        data: {
            'module': moduleName
        },
        ajax: true,
    });
}

function onClickModuleDetailUpdateButton(evt) {
    var btn = evt.target;
    var btnModuleName = btn.getAttribute('module');
    var installSize = OC.updates[btnModuleName].size;
    $.ajax({
        url: '/store/freemodulesspace',
        ajax: true,
        success: function(response) {
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
                OC.mediator.publish('showyesnodialog', mdiv, null, noSpace, justOk);
                return;
            } else {
                var buttonText = null;
                if (OC.installQueue.length == 0) {
                    buttonText = 'Updating...';
                } else {
                    buttonText = 'Queued';
                }
                queueInstall(btnModuleName, OC.updates[btnModuleName].version);
                btn.textContent = buttonText;
                btn.style.color = 'red';
                document.getElementById('moduledetaildiv_store').style.display = 'none';
                if (OC.installQueue.length == 0) {
                    setModuleTileAbortButton(btnModuleName);
                } else {
                    setModuleTileUnqueueButton(btnModuleName);
                }
            }
        },
    });
}


function writeInstallationMsg(msg) {
    var div = document.querySelector("#installationprogressmsgdiv");
    var tdiv = getEl("div");
    tdiv.textContent = msg;
    div.prepend(tdiv);
    var chaticondiv = document.querySelector('#chaticondiv')
    if (chaticondiv.classList.contains('hide') == false) {
        chaticondiv.classList.add('new')
    }
}



function getHighestVersionForRemoteModule(module) {
    var versions = OC.remoteModuleInfo[module].versions;
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

function queueInstall(moduleName, version) {
    $.get('/store/queueinstall', {
        'module': moduleName,
        'version': version
    }).done(
        function(response) {
            var keys = Object.keys(OC.installInfo);
            if (keys.length == 0) {
                OC.installInfo[moduleName] = {
                    'msg': 'installing'
                };
            } else {
                OC.installInfo[moduleName] = {
                    'msg': 'queued'
                };
            }
            OC.installQueue.push(moduleName);
            if (OC.baseInstalled) {
                populateAllModulesDiv();
            }
        }
    );
}

function uninstallModule(moduleName) {
    OC.installInfo[moduleName] = {
        'msg': 'uninstalling'
    };
    populateAllModulesDiv();
    writeInstallationMsg(getTimestamp() + " Uninstalling " + moduleName)
    $.ajax({
        type: 'GET',
        url: '/store/uninstall',
        data: {
            name: moduleName
        },
        complete: function(response) {
            delete OC.installInfo[moduleName];
            moduleChange(response);
            populateAnnotators();
            writeInstallationMsg(getTimestamp() + " Uninstalled " + moduleName)
        }
    });
}

function moduleChange(data) {
    getLocal();
}

function setServerStatus(connected) {
    var overlay = document.getElementById('store-noconnect-div');
    if (!connected) {
        overlay.style.display = 'block';
    } else {
        overlay.style.display = 'none';
    }
}

function setModuleTileInstallButton(module) {
    $('div.moduletile[module=' + module + ']').each(function(i, div) {
        $(div).children('button').remove();
        var button = getModuleTileInstallButton(module);
        addEl(div, button);
        $(div).children('div.panelinstallprogressspan').text('');
    });
}

function unqueue(moduleName) {
    var idx = OC.installQueue.indexOf(moduleName);
    if (idx >= 0) {
        OC.installQueue.splice(idx, 1);
    }
}

function checkConnection(failures) {
    failures = failures !== undefined ? failures : 0;
    var host = window.location.host;
    if (failures >= 3) {
        setServerStatus(false);
    }
    var protocol = window.location.protocol;
    var ws = null;
    if (protocol == 'http:') {
        ws = new WebSocket('ws://' + host + '/heartbeat');
    } else if (protocol == 'https:') {
        ws = new WebSocket('wss://' + host + '/heartbeat');
    }
    ws.onopen = function(evt) {
        setServerStatus(true);
        failures = 0;
    }
    ws.onclose = function(evt) {
        failures += 1;
        var waitTime = 2000 * failures;
        setTimeout(function() {
            checkConnection(failures);
        }, waitTime)
    }
    ws.onerror = function(evt) {}
    ws.onmessage = function(evt) {}
}

function connectWebSocket() {
    var host = window.location.host;
    var protocol = window.location.protocol;
    var ws = null;
    if (protocol == 'http:') {
        ws = new WebSocket('ws://' + host + '/store/connectwebsocket');
    } else if (protocol == 'https:') {
        ws = new WebSocket('wss://' + host + '/store/connectwebsocket');
    }
    ws.onopen = function(evt) {}
    ws.onclose = function(evt) {
        console.log('Re-establishing websocket');
        connectWebSocket();
    }
    ws.onmessage = function(evt) {
        var data = JSON.parse(evt.data);
        var module = data['module'];
        var msg = data['msg'];
        var isbase = data['isbase'];
        if (OC.installInfo[module] == undefined) {
            OC.installInfo[module] = {};
        }
        OC.installInfo[module]['msg'] = msg;
        var installstatdiv = null;
        if (OC.baseToInstall.length > 0 || OC.baseInstalled == false) {
            installstatdiv = document.getElementById('store-systemmodule-msg-div');
        } else {
            var divModuleName = module;
            installstatdiv = document.getElementById('installstatdiv_' + divModuleName);
        }
        if (installstatdiv != null) {
            installstatdiv.textContent = msg;
        }
        //var sdivs = $('div.moduletile[module=' + module + '] .panelinstallprogressspan');
        //for (var i1 = 0; i1 < sdivs.length; i1++) {
        //    var sdiv = sdivs[i1];
        //    sdiv.style.color = 'black';
        //    sdiv.textContent = msg;
        //}
        writeInstallationMsg(msg)
        if (msg.search('Finished installation of') > 0) {
            delete OC.installInfo[module];
            //installQueue = installQueue.filter(e => e != module);
            unqueue(module);
            moduleChange(null);
            populateAnnotators();
            if (OC.installQueue.length > 0) {
                var module = OC.installQueue.shift();
                OC.installInfo[module] = {
                    'msg': 'installing'
                };
            }
        } else if (msg.search('Aborted') > 0) {
            delete OC.installInfo[module];
            unqueue(module);
            setModuleTileInstallButton(module);
        } else if (msg.search('Unqueued') > 0) {
            delete OC.installInfo[module];
            unqueue(module);
            setModuleTileInstallButton(module);
        } else {
            var idx = OC.uninstalledModules.indexOf(module);
            if (idx >= 0) {
                setModuleTileAbortButton(module);
                OC.uninstalledModules.splice(idx, 1);
            }
        }
    }
}

function setModuleTileAbortButton(module) {
    $('div.moduletile[module=' + module + ']').each(function(i, div) {
        $(div).children('button').remove();
        var button = getModuleTileAbortButton(module);
        addEl(div, button);
    });
}

function getBaseModuleNames() {
    $.get('/store/getbasemodules').done(function(response) {
        OC.baseModuleNames = response;
    });
}

function onStoreTagCheckboxChange() {
    updateFilter();
}



function onClickStoreInstallAllButton() {
    $.ajax({
        url: '/store/freemodulesspace',
        async: true,
        success: function(response) {
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
                totalSizeN += OC.remoteModuleInfo[notInstalledModuleNames[i]].size;
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
            var yescallback = function(yn) {
                if (yn == true) {
                    for (var i = 0; i < notInstalledModuleNames.length; i++) {
                        queueInstall(notInstalledModuleNames[i]);
                    }
                }
            };
            OC.mediator.publish('showyesnodialog', div, yescallback, noSpace);
        },
    });
}

function getSystemModulesToUpdate() {
    var modulesToUpdate = [];
    for (var i = 0; i < OC.baseModuleNames.length; i++) {
        var moduleName = OC.baseModuleNames[i];
        var module = OC.origRemoteModuleInfo[moduleName];
        if (module['tags'].indexOf('newavailable') >= 0) {
            if (!OC.updateConflicts.hasOwnProperty(moduleName)) {
                modulesToUpdate.push(moduleName);
            }
        }
    }
    return modulesToUpdate;
}

function getModulesToUpdate() {
    var modulesToUpdate = [];
    for (var moduleName in OC.updates) {
        if (OC.remoteModuleInfo[moduleName] != undefined) {
            if (OC.remoteModuleInfo[moduleName]['tags'].indexOf('newavailable') >= 0) {
                if (!OC.updateConflicts.hasOwnProperty(moduleName)) {
                    modulesToUpdate.push(moduleName);
                }
            }
        }
    }
    return modulesToUpdate;
}

function onClickSystemModuleUpdateButton() {
    var modulesToUpdate = getSystemModulesToUpdate();
    var div = getEl('div');
    var updateModuleNames = Object.keys(OC.updates);
    var totalSizeN = 0;
    OC.baseToInstall = [];
    for (var i = 0; i < updateModuleNames.length; i++) {
        var moduleName = updateModuleNames[i];
        var module = OC.updates[moduleName];
        if (OC.baseModuleNames.includes(moduleName)) {
            OC.baseToInstall.push(moduleName);
            totalSizeN += module['size'];
        }
    }
    $.ajax({
        url: '/store/freemodulesspace',
        ajax: true,
        success: function(response) {
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
                var yescallback = function(yn) {
                    if (yn == true) {
                        startUpdatingSystemModules();
                    }
                };
            }
            OC.mediator.publish('showyesnodialog', div, yescallback, noSpace);
        },
    });
}

function startUpdatingSystemModules() {
    document.getElementById('store-systemmodule-msg-div').textContent = '';
    showSystemModulePage();
    document.getElementById('store-systemmodule-update-div').style.display = 'block';
    for (var i = 0; i < OC.baseToInstall.length; i++) {
        queueInstall(OC.baseToInstall[i]);
    }
}

function onClickStoreUpdateAllButton() {
    var modulesToUpdate = getModulesToUpdate();
    var div = getEl('div');
    var span = getEl('span');
    span.textContent = 'Modules to update are:';
    addEl(div, span);
    addEl(div, getEl('br'));
    addEl(div, getEl('br'));
    var totalSizeN = 0;
    for (var i = 0; i < modulesToUpdate.length; i++) {
        totalSizeN += OC.updates[modulesToUpdate[i]].size;
        var span = getEl('span');
        span.textContent = modulesToUpdate[i];
        span.style.fontWeight = 'bold';
        addEl(div, span);
        addEl(div, getEl('br'));
    }
    $.ajax({
        url: '/store/freemodulesspace',
        ajax: true,
        success: function(response) {
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
                var yescallback = function(yn) {
                    if (yn == true) {
                        announceStoreUpdatingAll();
                        for (var i = 0; i < modulesToUpdate.length; i++) {
                            queueInstall(modulesToUpdate[i]);
                        }
                    }
                };
            }
            OC.mediator.publish('showyesnodialog', div, yescallback, noSpace);
        },
    });
}

function announceStoreUpdatingAll() {
    var button = document.getElementById('store-update-all-button');
    button.style.display = 'none';
}

function announceStoreUpdateAllAvailable() {
    //var span = document.getElementById('store-update-all-span');
    //span.textContent = 'Updates to your installed modules are available!';
    var button = document.getElementById('store-update-all-button');
    button.style.display = 'inline';
    var div = document.getElementById('update-available-div')
    div.classList.add('active')
}

function disableUpdateAvailable() {
    var div = document.getElementById('update-available-div')
    div.classList.remove('active')
}

function webstore_run() {
    document.addEventListener('click', function(evt) {
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

// Bind events to the mediator
function addWebstoreEventHandlers() {
    OC.mediator.subscribe('system.update', onClickSystemModuleUpdateButton);
    OC.mediator.subscribe('getRemote', getRemote);
    OC.mediator.subscribe('moduleinfo.local', setupJobsTab);
    OC.mediator.subscribe('moduleinfo.local', setBaseInstalled);
    OC.mediator.subscribe('moduleinfo.local', populateStorePages);
    OC.mediator.subscribe('moduleinfo.updates', showOrHideSystemModuleUpdateButton);
    OC.mediator.subscribe('moduleinfo.updates', showOrHideUpdateAllButton);
    OC.mediator.subscribe('moduleinfo.local', populateStoreTagPanel);
    OC.mediator.subscribe('moduleinfo.install', onClickModuleInstallButton);
    OC.mediator.subscribe('moduleinfo.uninstall', uninstallModule);
    OC.mediator.subscribe('moduleinfo.update', onClickModuleDetailUpdateButton);

    // index.html webstore events
    $('#progressdivcloseicon').on('click', onClickProgressDivCloseIcon);
    $('#store-namefilter').on('input', updateFilter);
    $('#store-tag-checkbox-home').on('click', onClickStoreHome);
    $('#store-tag-checkbox-viewall').on('click', onClickStoreTagResetButton);
    $('#store-tag-checkbox-newavailable').on('click', onStoreTagCheckboxChange);
    $('#store-tag-checkbox-packages').on('click', onStoreTagCheckboxChange);
    $('.carousel-left').on('click', onClickStoreHomeLeftArrow);
    $('.carousel-right').on('click', onClickStoreHomeRightArrow);
    $('#store-sort-select').on('change', () => populateAllModulesDiv(true));
    $('#store-update-all-button').on('click', onClickStoreUpdateAllButton);
    $('#module-group-back-arrow').on('click', onClickModuleGroupDivBackArrow);
    $('#store-systemmodule-install-button').on('click', onClickInstallBaseComponents);

}

$(document).ready(() => addWebstoreEventHandlers());

export {
    addWebstoreEventHandlers,
    connectWebSocket,
    checkConnection,
    getBaseModuleNames,
    toggleChatBox
};