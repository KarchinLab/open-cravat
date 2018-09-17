var available;
var installed;
var currentDetailModule = null;

var remoteModuleInfo = {};
var localModuleInfo = {};
var filter = {'type': 'annotator'};
var installQueue = [];
var installInfo = {};
var baseModuleNames = [];

var storeUrl = null;
var storeurl = $.get('/store/getstoreurl').done(function(response) {
    storeUrl = response;
});

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

function getLocal () {
	$.get('/store/local').done(function(data){
        localModuleInfo = data;
        var localModuleNames = Object.keys(localModuleInfo);
        var baseInstalled = true;
        for (var i = 0; i < baseModuleNames.length; i++) {
            var baseModuleName = baseModuleNames[i];
            if (localModuleNames.includes(baseModuleName) == false) {
                baseInstalled = false;
                break;
            }
        }
        var div = document.getElementById('remotemodulepanels');
        if (div == null) {
            return;
        }
        if (baseInstalled) {
            var div = document.getElementById('messagediv');
            div.style.display = 'none';
            div = document.getElementById('remotemodulepanels');
            div.style.top = '120px';
            var select = document.getElementById('typefilter');
            select.disabled = false;
            var input = document.getElementById('namefilter');
            input.disabled = false;
            var div = document.getElementById('moduledetaildiv');
            if (div != null) {
                if (div.style.display != 'none') {
                    activateDetailDialog(currentDetailModule);
                }
            }
            updateRemotePanels();
        } else {
            var div = document.getElementById('messagediv');
            emptyElement(div);
            div.style.top = '120px';
            div.style.display = 'block';
            var span = getEl('span');
            span.style.position = 'relative';
            span.style.top = '40px';
            span.textContent = 'All base modules need to be installed to use Open-CRAVAT. Click this button to install them all: ';
            addEl(div, span);
            var button = getEl('button');
            button.style.position = 'relative';
            button.style.top = '37px';
            button.textContent = 'Install base components';
            button.addEventListener('click', function (evt) {
                installBaseComponents();
            });
            addEl(div, button);
            div = document.getElementById('remotemodulepanels');
            div.style.top = '220px';
            document.getElementById('typefilter').value = 'base';
            updateFilter();
            var select = document.getElementById('typefilter');
            select.disabled = true;
            var input = document.getElementById('namefilter');
            input.disabled = true;
        }
	});
}

function installBaseComponents () {
    for (var i = 0; i < baseModuleNames.length; i++) {
        var module = baseModuleNames[i];
        if (localModuleInfo[module] == undefined || localModuleInfo[module]['exists'] == false) {
            queueInstall(module);
        }
    }
}

function getRemote () {
	$.get('/store/remote').done(function(data){
        remoteModuleInfo = data;
        var modules = Object.keys(remoteModuleInfo);
        for (var i = 0; i < modules.length; i++) {
            var module = modules[i];
            var moduleInfo = remoteModuleInfo[module];
            if (moduleInfo['queued'] == true) {
                installInfo[module] = {'msg': 'queued'};
            }
        }
        populateTypeFilter();
	});
}

function populateTypeFilter () {
    var moduleNames = Object.keys(remoteModuleInfo);
    var types = [''];
    var select = document.getElementById('typefilter');
    if (select == null) {
        return;
    }
    types.push('base');
    for (var i = 0; i < moduleNames.length; i++) {
        var moduleName = moduleNames[i];
        var info = remoteModuleInfo[moduleName];
        var type = info['type'];
        if (types.includes(type)) {
            continue;
        } else if (type == 'aggregator' || type == 'postaggregator') {
            continue;
        } else {
            types.push(type);
        }
    }
    types.sort();
    for (var i = 0; i < types.length; i++) {
        var option = getEl('option');
        var type = types[i];
        option.value = type;
        option.innerText = type;
        if (type == filter['type']) {
            option.selected = true;
        }
        addEl(select, option);
    }
}

function emptyElement (elem) {
	var last = null;
    while (last = elem.lastChild) {
    	elem.removeChild(last);
    }
}

function updateFilter () {
    var nameinput = document.getElementById('namefilter');
    var nameStr = nameinput.value;
    filter = {};
    if (nameStr != '') {
        filter['name'] = [nameStr];
    }
    var typeStr = document.getElementById('typefilter').value;
    if (typeStr != '') {
        filter['type'] = typeStr;
    }
    updateRemotePanels();
}

function getFilteredRemoteModules () {
    var filteredRemoteModules = {};
    var remoteModuleNames = Object.keys(remoteModuleInfo);
    var hasFilter = Object.keys(filter).length > 0;
    for (var i = 0; i < remoteModuleNames.length; i++) {
        var remoteModuleName = remoteModuleNames[i];
        var remoteModuleNameLower = remoteModuleName.toLowerCase();
        var remoteModule = remoteModuleInfo[remoteModuleName];
        if (hasFilter) {
            var typeYes = false;
            var nameYes = false;
            if (filter['type'] != undefined && filter['type'] != '') {
                if (filter['type'] == 'base') {
                    if (baseModuleNames.includes(remoteModuleName)) {
                        typeYes = true;
                    } else {
                        typeYes = false;
                    }
                } else {
                    if (filter['type'].includes(remoteModule['type'])) {
                        typeYes = true;
                    } else {
                        typeYes = false;
                    }
                }
            } else {
                typeYes = true;
            }
            if (filter['name'] != undefined && filter['name'] != '') {
                var nameYes = false;
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
        } else {
            typeYes = true;
            nameYes = true;
        }
        if (typeYes && nameYes) {
            filteredRemoteModules[remoteModuleName] = remoteModule;
        }
    }
    return filteredRemoteModules;
}

function updateRemotePanels () {
    var div = document.getElementById('remotemodulepanels');
    emptyElement(div);
    var remoteModuleNames = Object.keys(getFilteredRemoteModules());
    for (var i = 0; i < remoteModuleNames.length; i++) {
        var remoteModuleName = remoteModuleNames[i];
        if (remoteModuleName.startsWith('chasmplus_')) {
            continue;
        }
        if (remoteModuleName == 'example_annotator' || remoteModuleName == 'template') {
            continue;
        }
        var remoteModule = remoteModuleInfo[remoteModuleName];
        var panel = getRemoteModulePanel(remoteModuleName);
        addEl(div, panel);
    }
}

function getLogo (moduleName) {
    var moduleInfo = remoteModuleInfo[moduleName];
    var img = getEl('img');
    var logoUrl = storeUrl + '/modules/' + moduleName + '/' + moduleInfo['latest_version'] + '/logo.png';
    img.src = logoUrl;
    img.style.maxWidth = '100%';
    img.style.maxHeight = '100%';
    img.style.width = 'auto';
    img.style.height = 'auto';
    return img;
}

function activateDetailDialog (moduleName) {
    var div = document.getElementById('moduledetaildiv');
    if (div) {
        emptyElement(div);
    } else {
        div = getEl('div');
        div.id = 'moduledetaildiv';
        div.style.position = 'fixed';
        div.style.width = '80%';
        div.style.height = '80%';
        div.style.margin = 'auto';
        div.style.zIndex = '1';
        div.style.backgroundColor = 'white';
        div.style.left = '0';
        div.style.right = '0';
        div.style.top = '0';
        div.style.bottom = '0';
        div.style.zIndex = '1';
        div.style.border = '6px';
        div.style.padding = '10px';
        div.style.paddingBottom = '23px';
        div.style.border = '1px solid black';
        div.style.boxShadow = '0px 0px 20px';
    }
    currentDetailModule = moduleName;
    div.style.display = 'block';
    var moduleInfo = remoteModuleInfo[moduleName];
    var table = getEl('table');
    table.style.height = '100px';
    table.style.border = '0px';
    var tr = getEl('tr');
    tr.style.border = '0px';
    var td = getEl('td');
    td.id = 'moduledetaillogotd';
    td.style.width = '120px';
    td.style.border = '0px';
    addEl(tr, td);
    var img = getLogo(moduleName);
    img.onerror = function () {
        var span = getEl('div');
        span.style.fontSize = '20px';
        span.style.fontWeight = 'bold';
        span.textContent = moduleInfo.title;
        addEl(document.getElementById('moduledetaillogotd'), span);
    }
    img.onload = function () {
        addEl(document.getElementById('moduledetaillogotd'), this);
    }
    td = getEl('td');
    td.style.border = '0px';
    var span = getEl('div');
    span.style.fontSize = '30px';
    span.textContent = moduleInfo.title;
    addEl(td, span);
    addEl(td, getEl('br'));
    span = getEl('span');
    span.style.fontSize = '12px';
    span.style.color = 'green';
    span.textContent = moduleInfo.type;
    addEl(td, span);
    span = getEl('span');
    span.style.fontSize = '12px';
    span.style.color = 'green';
    span.textContent = ' | ' + moduleInfo.developer.organization;
    addEl(td, span);
    addEl(tr, td);
    td = getEl('td');
    td.style.border = '0px';
    td.style.verticalAlign = 'top';
    td.style.textAlign = 'right';
    var button = getEl('button');
    var localInfo = localModuleInfo[moduleName];
    var buttonText = null;
    if (localInfo != undefined && localInfo.exists) {
        buttonText = 'Uninstall';
        button.style.backgroundColor = '#ffd3be';
        button.addEventListener('click', function (evt) {
            var btn = evt.target;
            btn.textContent = 'Uninstalling...';
            btn.style.color = 'red';
            uninstallModule(btn.getAttribute('module'));
            document.getElementById('moduledetaildiv').style.display = 'none';
        });
    } else {
        buttonText = 'Install';
        button.style.backgroundColor = '#beeaff';
        button.addEventListener('click', function (evt) {
            var btn = evt.target;
            var btnModuleName = btn.getAttribute('module');
            if (btnModuleName == 'chasmplus') {
                var select = document.getElementById('chasmplustissueselect');
                btnModuleName = select.value;
            }
            var buttonText = null;
            if (installQueue.length == 0) {
                buttonText = 'Installing...';
            } else {
                buttonText = 'Queued';
            }
            queueInstall(btnModuleName);
            btn.textContent = buttonText;
            btn.style.color = 'red';
            document.getElementById('moduledetaildiv').style.display = 'none';
        });
    }
    button.textContent = buttonText;
    //button.style.border = '0px';
    //button.style.boxShadow = '3px 3px 2px #888888';
    button.style.padding = '8px';
    //button.style.borderRadius = '3px';
    button.style.fontSize = '18px';
    button.style.fontWeight = 'bold';
    button.setAttribute('module', moduleName);
    if (buttonText == 'Uninstall') {
        var img2 = getEl('img');
        img2.src = '/store/done.png';
        img2.style.width = '20px';
        img2.title = 'Installed';
        addEl(td, img2);
    }
    addEl(td, getEl('br'));
    if (moduleName == 'chasmplus') {
        var span = getEl('span');
        span.textContent = 'Select tissue:';
        addEl(td, span);
        var select = getEl('select');
        select.id = 'chasmplustissueselect';
        var option = getEl('option');
        option.value = 'chasmplus';
        option.text = 'Generic';
        select.add(option);
        var modules = Object.keys(remoteModuleInfo);
        for (var i = 0; i < modules.length; i++) {
            var module = modules[i];
            if (module.startsWith('chasmplus_')) {
                var option = getEl('option');
                var tissue = module.replace('chasmplus_', '');
                option.value = module;
                option.text = tissue;
                select.add(option);
            }
        }
        addEl(td, select);
    }
    addEl(td, button);
    var sdiv = getEl('div');
    sdiv.id = 'installstatdiv_' + moduleName;
    sdiv.style.marginTop = '10px';
    sdiv.style.fontSize = '12px';
    if (installInfo[moduleName] != undefined) {
        sdiv.textContent = installInfo[moduleName]['msg'];
    }
    addEl(td, sdiv);
    addEl(tr, td);
    addEl(table, tr);
    addEl(div, table);
    addEl(div, getEl('hr'));
    table = getEl('table');
    table.style.height = 'calc(100% - 100px)';
    table.style.border = '0px';
    tr = getEl('tr');
    tr.style.border = '0px';
    td = getEl('td');
    td.style.border = '0px';
    td.style.width = '70%';
    td.style.verticalAlign = 'top';
    var mdDiv = getEl('div');
    mdDiv.style.height = '100%';
    mdDiv.style.overflow = 'auto';
    addEl(td, mdDiv);
    addEl(tr, td);
	$.get('/store/modules/'+moduleName+'/'+'latest'+'/readme').done(function(data){
		mdDiv.innerHTML = data;
	});
    td = getEl('td');
    td.style.width = '30%';
    td.style.border = '0px';
    td.style.verticalAlign = 'top';
    var infodiv = getEl('div');
    var d = getEl('div');
    span = getEl('span');
    span.textContent = moduleInfo.description;
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Version: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = moduleInfo['latest_version'];
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Maintainer: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = moduleInfo['developer']['name'];
    addEl(d, span);
    addEl(d, getEl('br'));
    addEl(d, getEl('br'));
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'e-mail: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = moduleInfo['developer']['email'];
    addEl(d, span);
    addEl(d, getEl('br'));
    addEl(d, getEl('br'));
    addEl(infodiv, d);
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Citation: ';
    addEl(d, span);
    span = getEl('span');
    span.style.display = 'inline-block';
    span.style.width = 'calc(100% - 120px)';
    span.style.wordWrap = 'break-word';
    span.style.verticalAlign = 'text-top';
    var citation = moduleInfo['developer']['citation'];
    if (citation.startsWith('http')) {
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
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Organization: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = moduleInfo['developer']['organization'];
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Website: ';
    addEl(d, span);
    span = getEl('a');
    span.textContent = moduleInfo['developer']['website'];
    span.href = moduleInfo['developer']['website'];
    span.target = '_blank';
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Type: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = moduleInfo['type'];
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Size: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = getSizeText(moduleInfo['size']);
    addEl(d, span);
    addEl(infodiv, d);
    addEl(td, infodiv);
    addEl(tr, td);
    addEl(table, tr);
    addEl(div, table);
    return div;
}

function getModuleDetailDiv (moduleName) {
    var div = document.getElementById('moduledetaildiv');
    if (div) {
        emptyElement(div);
    } else {
        div = getEl('div');
        div.id = 'moduledetaildiv';
        div.style.position = 'fixed';
        div.style.width = 'calc(90% - 200px)';
        div.style.height = '80%';
        div.style.margin = 'auto';
        div.style.zIndex = '1';
        div.style.backgroundColor = 'white';
        div.style.left = '200px';
        div.style.right = '0';
        div.style.top = '0';
        div.style.bottom = '0';
        div.style.zIndex = '1';
        div.style.border = '6px';
        div.style.padding = '10px';
        div.style.paddingBottom = '23px';
        div.style.border = '1px solid black';
        div.style.boxShadow = '0px 0px 20px';
    }
    currentDetailModule = moduleName;
    div.style.display = 'block';
    var localModule = localModuleInfo[moduleName];
    var table = getEl('table');
    table.style.height = '100px';
    table.style.border = '0px';
    var tr = getEl('tr');
    tr.style.border = '0px';
    var td = getEl('td');
    td.id = 'moduledetaillogotd';
    td.style.width = '120px';
    td.style.border = '0px';
    addEl(tr, td);
    var img = getLogo(moduleName);
    img.onerror = function () {
        var span = getEl('div');
        span.style.fontSize = '20px';
        span.style.fontWeight = 'bold';
        span.textContent = localModule.title;
        var sdiv = div.querySelector('#moduledetaillogotd');
        addEl(sdiv, span);
    }
    img.onload = function () {
        var sdiv = div.querySelector('#moduledetaillogotd');
        addEl(sdiv, this);
    }
    addEl(tr, td);
    td = getEl('td');
    td.style.border = '0px';
    var span = getEl('div');
    span.style.fontSize = '30px';
    span.textContent = localModule.title;
    addEl(td, span);
    addEl(td, getEl('br'));
    span = getEl('span');
    span.style.fontSize = '12px';
    span.style.color = 'green';
    span.textContent = localModule.type;
    addEl(td, span);
    span = getEl('span');
    span.style.fontSize = '12px';
    span.style.color = 'green';
    span.textContent = ' | ' + localModule.developer.organization;
    addEl(td, span);
    addEl(tr, td);
    td = getEl('td');
    td.style.border = '0px';
    td.style.verticalAlign = 'top';
    td.style.textAlign = 'right';
    var sdiv = getEl('div');
    sdiv.id = 'installstatdiv_' + moduleName;
    sdiv.style.marginTop = '10px';
    sdiv.style.fontSize = '12px';
    if (installInfo[moduleName] != undefined) {
        sdiv.textContent = installInfo[moduleName]['msg'];
    }
    addEl(td, sdiv);
    addEl(tr, td);
    addEl(table, tr);
    addEl(div, table);
    addEl(div, getEl('hr'));
    table = getEl('table');
    table.style.height = 'calc(100% - 100px)';
    table.style.border = '0px';
    tr = getEl('tr');
    tr.style.border = '0px';
    td = getEl('td');
    td.style.border = '0px';
    td.style.width = '70%';
    td.style.verticalAlign = 'top';
    var mdDiv = getEl('div');
    mdDiv.style.height = '100%';
    mdDiv.style.overflow = 'auto';
    addEl(td, mdDiv);
    addEl(tr, td);
	$.get('/store/modules/'+moduleName+'/'+'latest'+'/readme').done(function(data){
		mdDiv.innerHTML = data;
	});
    td = getEl('td');
    td.style.width = '30%';
    td.style.border = '0px';
    td.style.verticalAlign = 'top';
    var infodiv = getEl('div');
    var d = getEl('div');
    span = getEl('span');
    span.textContent = localModule.description;
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Version: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = localModule['version'];
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Maintainer: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = localModule['developer']['name'];
    addEl(d, span);
    addEl(d, getEl('br'));
    addEl(d, getEl('br'));
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'e-mail: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = localModule['developer']['email'];
    addEl(d, span);
    addEl(d, getEl('br'));
    addEl(d, getEl('br'));
    addEl(infodiv, d);
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Citation: ';
    addEl(d, span);
    span = getEl('span');
    span.style.display = 'inline-block';
    span.style.width = 'calc(100% - 120px)';
    span.style.wordWrap = 'break-word';
    span.style.verticalAlign = 'text-top';
    var citation = localModule['developer']['citation'];
    if (citation.startsWith('http')) {
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
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Organization: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = localModule['developer']['organization'];
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Website: ';
    addEl(d, span);
    span = getEl('a');
    span.textContent = localModule['developer']['website'];
    span.href = localModule['developer']['website'];
    span.target = '_blank';
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Type: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = localModule['type'];
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    addEl(td, infodiv);
    addEl(tr, td);
    addEl(table, tr);
    addEl(div, table);
    return div;
}

function getSizeText (size) {
    size = parseInt(size);
    if (size < 1024) {
        size = size + ' B';
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

function queueInstall (moduleName) {
    $.get('/store/queueinstall', {'module': moduleName}).done(
        function (response) {
            installInfo[moduleName] = {'msg': 'queued'};
            installQueue.push(moduleName);
            updateRemotePanels();
        }
    );
}

function installModule (moduleName) {
	var version = remoteModuleInfo[moduleName]['latest_version'];
	$.ajax({
		type:'GET',
		url:'/store/install',
		data: {name:moduleName, version:version},
		dataType:'json',
	});
}

function uninstallModule(moduleName) {
    installInfo[moduleName] = {'msg': 'uninstalling'};
    updateRemotePanels();
	$.ajax({
			type:'GET',
			url:'/store/uninstall',
			data: {name: moduleName},
			dataType: 'json',
			complete: function (response) {
                delete installInfo[moduleName];
                moduleChange(response);
            }
	});
}

function moduleChange (data) {
	getLocal();
}

function connectWebSocket () {
    var ws = new WebSocket('ws://localhost:8060/store/connectwebsocket');
    ws.onopen = function (evt) {
    }
    ws.onmessage = function (evt) {
        //console.log('ws message:', evt.data);
        var data = JSON.parse(evt.data);
        var module = data['module'];
        var msg = data['msg'];
        var isbase = data['isbase'];
        if (installInfo[module] == undefined) {
            installInfo[module] = {};
        }
        installInfo[module]['msg'] = msg;
        if (isbase != undefined && isbase == true) {
            var installstatdiv = document.getElementById('installbasestatdiv');
            installstatdiv.textContent = msg;
        } else {
            var divModuleName = module;
            if (module.startsWith('chasmplus_')) {
                divModuleName = module.split('_')[0];
            }
            var installstatdiv = document.getElementById('installstatdiv_' + divModuleName);
            if (installstatdiv != null) {
                installstatdiv.textContent = msg;
            }
            var sdiv = document.getElementById('panelinstallstatus_' + divModuleName);
            sdiv.style.color = 'black';
            sdiv.textContent = msg;
            if (msg.startsWith('Finished installation of')) {
                delete installInfo[module];
                installQueue = installQueue.filter(e => e != module);
                moduleChange(null);
                if (installQueue.length > 0) {
                    var module = installQueue.shift();
                    installInfo[module] = {'msg': 'installing'};
                    queueInstall(module);
                }
            }
        }
    }
}

function getBaseModuleNames () {
    $.get('/store/getbasemodules').done(function (response) {
        baseModuleNames = response;
    });
}

function webstore_run () {
    document.addEventListener('click', function (evt) {
        if (evt.target.closest('#moduledetaildiv') == null) {
            var div = document.getElementById('moduledetaildiv');
            if (div != null) {
                div.style.display = 'none';
            }
        }
    });
    connectWebSocket();
    getBaseModuleNames();
	getRemote();
    getLocal();
}
