var available;
var installed;

//
var remoteModuleInfo = {};
var localModuleInfo = {};
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
        moduleInfoLocal = data;

	});
}

function getRemote () {
	$.get('/store/remote').done(function(data){
        remoteModuleInfo = data;
        updateRemotePanels();
	});
}

function emptyElement (elem) {
	var last = null;
    while (last = elem.lastChild) {
    	elem.removeChild(last);
    }
}

function updateRemotePanels () {
    var div = document.getElementById('remotemodulepanels');
    emptyElement(div);
    var remoteModuleNames = Object.keys(remoteModuleInfo);
    for (var i = 0; i < remoteModuleNames.length; i++) {
        var remoteModuleName = remoteModuleNames[i];
        if (remoteModuleName.startsWith('chasmplus_')) {
            continue;
        }
        var remoteModule = remoteModuleInfo[remoteModuleName];
        if (remoteModule['type'] == 'annotator') {
            var panel = getRemoteModulePanel(remoteModuleName);
            addEl(div, panel);
        }
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

function getRemoteModulePanel (moduleName) {
    var moduleInfo = remoteModuleInfo[moduleName];
    var div = getEl('div');
    div.style.display = 'inline-block';
    div.style.width = '300px';
    div.style.height = '300px';
    div.style.borderWidth = '2px';
    div.style.borderColor = '#dddddd';
    div.style.borderStyle = 'ridge';
    div.style.verticalAlign = 'top';
    div.style.margin = '2px';
    div.style.padding = '2px';
    //div.style.backgroundColor = '#ffffaa';
    div.style.position = 'relative';
    div.setAttribute('module', moduleName);
    var span = getEl('span');
    addEl(span, getTn(moduleInfo.title));
    addEl(div, span);
    var img = getLogo(moduleName);
    img.onerror = function () {
        var span = getEl('div');
        span.style.fontSize = '42px';
        span.style.fontWeight = 'bold';
        span.textContent = moduleInfo.title;
        span.style.display = 'inline-table';
        span.style.position = 'absolute';
        span.style.bottom = '0';
        span.style.top = '0';
        span.style.left = '0';
        span.style.right = '0';
        span.style.margin = 'auto';
        span.style.width = '100%';
        span.style.height = 'auto';
        span.style.maxWidth = '100%';
        span.style.maxHeight = '100%';
        span.style.textAlign = 'center';
        span.onclick = function (evt) {
            console.log(evt);
            var pdiv = evt.target.parentElement;
            var moduleName = pdiv.getAttribute('module');
            console.log(moduleName);
            var dialog = activateDetailDialog(moduleName);
            addEl(document.body, dialog);
        }
        addEl(div, span);
    }
    img.onload = function () {
        img.style.top = '0';
        img.style.bottom = '0';
        img.style.left = '0';
        img.style.right = '0';
        img.style.margin = 'auto';
        img.style.position = 'absolute';
        img.style.width = 'auto';
        img.style.height = 'auto';
        img.style.maxWidth = '100%';
        img.style.maxHeight = '100%';
        img.onclick = function (evt) {
            console.log(evt);
            var pdiv = evt.target.parentElement;
            var moduleName = pdiv.getAttribute('module');
            console.log(moduleName);
            var dialog = activateDetailDialog(moduleName);
            addEl(document.body, dialog);
        }
        addEl(div, img);
    }
    return div
}

function activateDetailDialog (moduleName) {
    var div = document.getElementById('moduledetaildiv');
    if (div) {
        emptyElement(div);
    } else {
        div = getEl('div');
        div.id = 'moduledetaildiv';
        div.style.position = 'fixed';
        div.style.width = '90%';
        div.style.height = '90%';
        div.style.margin = 'auto';
        div.style.zIndex = '1';
        div.style.backgroundColor = 'white';
        div.style.left = '0';
        div.style.right = '0';
        div.style.top = '0';
        div.style.bottom = '0';
        div.style.zIndex = '1';
        div.style.border = '6px';
        div.style.borderStyle = 'groove';
        div.style.padding = '10px';
    }
    var moduleInfo = remoteModuleInfo[moduleName];
    var table = getEl('table');
    table.style.height = '100px';
    var tr = getEl('tr');
    var td = getEl('td');
    td.id = 'moduledetaillogotd';
    td.style.width = '120px';
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
    addEl(tr, td);
    td = getEl('td');
    var span = getEl('span');
    span.style.fontSize = '30px';
    span.textContent = moduleInfo.title;
    addEl(td, span);
    addEl(tr, td);
    td = getEl('td');
    var button = getEl('button');
    button.textContent = 'ADD TO CRAVAT';
    button.style.backgroundColor = '#82b7ef';
    button.style.border = '0px';
    button.style.boxShadow = '3px 3px 2px #888888';
    button.style.padding = '8px';
    button.setAttribute('module', moduleName);
    button.addEventListener('click', function (evt) {
        installModule(evt.target.getAttribute('module'));
    });
    addEl(td, button);
    addEl(tr, td);
    addEl(table, tr);
    addEl(div, table);
    table = getEl('table');
    table.style.height = 'calc(100% - 100px)';
    tr = getEl('tr');
    td = getEl('td');
    td.style.width = '70%';
    var mdDiv = getEl('div');
    addEl(td, mdDiv);
    addEl(tr, td);
	$.get('/store/modules/'+moduleName+'/'+'latest'+'/readme').done(function(data){
		mdDiv.html(data);
	});
    td = getEl('td');
    td.style.width = '30%';
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
    span.textContent = 'Version:';
    addEl(d, span);
    span = getEl('span');
    span.textContent = moduleInfo['latest_version'];
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    /*
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.style.fontSize = '16px';
    span.textContent = 'Developer';
    addEl(d, span);
    addEl(d, getEl('br'));
    */
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Maintainer:';
    addEl(d, span);
    span = getEl('span');
    span.textContent = moduleInfo['developer']['name'];
    addEl(d, span);
    addEl(d, getEl('br'));
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'e-mail:';
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
    span.textContent = 'Citation:';
    addEl(d, span);
    span = getEl('span');
    span.style.display = 'inline-block';
    span.style.width = 'calc(100% - 120px)';
    span.style.wordWrap = 'break-word';
    span.style.verticalAlign = 'text-top';
    span.textContent = moduleInfo['developer']['citation'];
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Organization:';
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
    addEl(td, infodiv);
    addEl(tr, td);
    addEl(table, tr);
    addEl(div, table);
    return div;
}

function installModule (moduleName) {
	var version = remoteModuleInfo[moduleName]['latest_version'];
	$.ajax({
		type:'GET',
		url:'/store/install',
		data: {name:moduleName, version:version},
		dataType:'json',
		complete: moduleChange
	});
}

function moduleChange(data) {
	//getLocal();
}

function mainTableRowClickHandler (event) {
	var td = event.target;
	if (td.nodeName=='TD') {
		var tr = td.parentNode;
		var moduleName = tr.getAttribute('moduleName');
		showModuleInfo(moduleName, selectedVersions[moduleName]);
	}
}

function addModuleInfoDivCloseListener() {
	var close_div = $('#module_info_closer');
	close_div.on('click',hideModuleInfoDiv);
}

function showModuleInfo (moduleName, version) {
	showModuleInfoDiv(moduleName, version);
}

function loadModuleInfo(moduleName, version, callback) {
	$.get('/store/remote/'+moduleName+'/'+version).done(function(data){
		remote[moduleName].versionInfo[version] = data;
		callback();
	});
}

function showModuleInfoDiv (moduleName, version) {
	var moduleInfo = remote[moduleName];
	var moduleInfoDiv = $('#module_info_div');
	addModuleInfoDivCloseListener();
	var content = $('#module_info_content');
	var titleDiv = $('#module_info_title');
	titleDiv.empty();
	titleDiv.html(moduleInfo.title);
	var summaryDiv = $('#module_info_summary');
	summaryDiv.empty();
	// Summary
	// Installed
	var installed = local.hasOwnProperty(moduleName)
	if (installed) {
		summaryDiv.append(getTn('Installed'));
		summaryDiv.append(getEl('br'));
		summaryDiv.append(getTn('Version: '+local[moduleName].version));
	} else {
		summaryDiv.append(getTn('Not Installed'));
	}
	summaryDiv.append(getEl('br'));
	// Latest Version
	summaryDiv.append(getTn('Latest version: '+remote[moduleName].latest_version));
	summaryDiv.append(getEl('br'));
	// Version Select
	var select = getEl('select');
	select.classList.add('version_selector');
	select.setAttribute('module_name',moduleName);
	var versions = remote[moduleName]['versions'];
	for (var i=0; i<versions.length; i++) {
		var v = versions[i];
		var opt = getEl('option');
		addEl(select, opt);
		opt.value = v;
		opt.innerText = v;
	}
	select.value=version;
	select.addEventListener('change',versionSelectChange);
	summaryDiv.append(select);
	// Install/Update
	var btn = getEl('button');
	btn.id = moduleName+'_install_btn';
	btn.classList.add('install_uninstall_btn');
	btn.setAttribute('module_name',moduleName);
	btn.innerText = 'Install';
	btn.addEventListener('click',installUpdateCallback);
	summaryDiv.append(btn);
	summaryDiv.append(getEl('br'));
	// Uninstall
	var btn = getEl('button');
	btn.id = moduleName+'_uninstall_btn';
	btn.classList.add('install_uninstall_btn');
	btn.setAttribute('module_name',moduleName);
	btn.innerText = 'Uninstall';
	btn.addEventListener('click',uninstallModuleCallback);
	btn.disabled = !(local.hasOwnProperty(moduleName));
	summaryDiv.append(btn);
	moduleInfoDiv.show()
	// Details
	var detailDiv = $('#module_info_details');
	detailDiv.empty();
	$.get('/store/modules/'+moduleName+'/'+version+'/readme').done(function(data){
		detailDiv.html(data);
	});
}

function hideModuleInfoDiv () {
	var moduleInfoDiv = $('#module_info_div')
	moduleInfoDiv.hide()
}

var selectedVersions = {};

function buildTable () {
	var table = document.getElementById('status_table');
	while(table.firstChild) {
		table.removeChild(table.firstChild);
	}
	var headers = ['Module',
	               'Installed',
	               'Installed Version',
	               'Latest Version',
	               'Install',
	               'Uninstall'];
	var tr = getEl('tr')
	addEl(table, tr);
	for (var i=0; i<headers.length; i++) {
		var th = getEl('th');
		addEl(tr, th)
		th.innerText = headers[i];
	}
	for (var moduleName in remote) {
		var tr = getEl('tr');
		addEl(table, tr);
		tr.classList.add('main_table_row');
		tr.addEventListener('click',mainTableRowClickHandler)
		tr.setAttribute('modulename',moduleName);
		tr.id = moduleName+'_info_row'
		// Module
		var td = getEl('td');
		addEl(tr, td);
		td.innerText = moduleName;
		// Installed
		var td = getEl('td');
		addEl(tr, td);
		var installed = local.hasOwnProperty(moduleName)
		if (installed) {
			td.innerText = 'Yes';
		} else {
			td.innerText = 'No';
		}
		// Installed Version
		var td = getEl('td');
		addEl(tr, td);
		if (installed) {
			td.innerText = local[moduleName].version;
		}
		// Latest Version
		var td = getEl('td');
		addEl(tr, td);
		td.innerText = remote[moduleName].latest_version;
		
		// Install/Update
		var td = getEl('td');
		addEl(tr, td);
		var select = getEl('select');
		addEl(td, select);
		select.classList.add('version_selector');
		select.setAttribute('module_name',moduleName);
		var versions = remote[moduleName]['versions'];
		for (var i=0; i<versions.length; i++) {
			var v = versions[i];
			var opt = getEl('option');
			addEl(select, opt);
			opt.value = v;
			opt.innerText = v;
		}
		if (selectedVersions.hasOwnProperty(moduleName)) {
			select.value = selectedVersions[moduleName];
		} else {
			var latestVersion = remote[moduleName]['latest_version'];
			select.value = latestVersion;
			selectedVersions[moduleName]= latestVersion;
		}
		select.addEventListener('change',versionSelectChange);
		var btn = getEl('button');
		addEl(td, btn);
		btn.id = moduleName+'_install_btn';
		btn.classList.add('install_uninstall_btn');
		btn.setAttribute('module_name',moduleName);
		btn.innerText = 'Install';
		btn.addEventListener('click',installUpdateCallback);
		
		// Uninstall
		var td = getEl('td');
		addEl(tr, td);
		var btn = getEl('button');
		addEl(td, btn);
		btn.id = moduleName+'_uninstall_btn';
		btn.classList.add('install_uninstall_btn');
		btn.setAttribute('module_name',moduleName);
		btn.innerText = 'Uninstall';
		btn.addEventListener('click',uninstallModuleCallback);
		btn.disabled = !(local.hasOwnProperty(moduleName));
	}
}


function versionSelectChange(event) {
	var selector = event.target;
	var version = selector.value;
	var moduleName = selector.getAttribute('module_name');
	selectedVersions[moduleName] = version;
}

function installUpdateCallback(event) {
	var btn = event.target;
	var moduleName = btn.getAttribute('module_name');
	installModule(moduleName);
}

function uninstallModuleCallback(event) {
	var btn = event.target;
	var moduleName = btn.getAttribute('module_name');
	uninstallModule(moduleName);
}

function uninstallModule(moduleName) {
	console.log('Uninstall '+moduleName);
	var d = {name:moduleName};
	$.ajax({
			type:'POST',
			url:'/uninstall',
			data:JSON.stringify(d),
			dataType:'json',
			complete: moduleChange
	});
}

function connectInstallStream(clbk) {
	var evtSource = new EventSource("/store/installstream");
	evtSource.onmessage = clbk;
}

function logInstallStream() {
	function logIt (e) {
		console.log(e.data);
	}
	var div = document.getElementById('install_stream');
	function updateDiv (e) {
		var stage = JSON.parse(e.data);
		var lastUpdate = new Date(stage.update_time);
		var t = stage.message;
		t += '\nChunks: '+stage.cur_chunk+'/'+stage.total_chunks;
		t += '\nBytes: '+stage.cur_size+'/'+stage.total_size;
		t += '\nLast Update: '+lastUpdate.toTimeString();
		div.innerText = t;
		if (stage.stage=='finish') {
			getLocal();
		}
	}
	connectInstallStream(updateDiv);
}

function run () {
	getRemote();
    //getLocal();
	//logInstallStream()
}
