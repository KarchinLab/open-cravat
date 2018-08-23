var available;
var installed;

function getEl(tag){
	var new_node = document.createElement(tag);
	return new_node;
}

function getTn(text){
	var new_text_node = document.createTextNode(text);
	return new_text_node;
}

function addEl (parent, child) {
	parent.appendChild(child);
	return parent;
}

function getLocal () {
	$.get('/local').done(function(data){
			local = data;
			buildTable();
	});
}

function getRemote () {
	$.get('/remote').done(function(data){
		remote = data;
		for (moduleName in remote) {
			selectedVersions[moduleName] = remote[moduleName]['latest_version'];
		}
		getLocal();
	});
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
	$.get('rest/remote/'+moduleName+'/'+version).done(function(data){
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
	$.get('/modules/'+moduleName+'/'+version+'/readme').done(function(data){
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

function installModule(moduleName) {
	version = selectedVersions[moduleName];
	var d = {name:moduleName,version:version};
	$.ajax({
		type:'POST',
		url:'/install',
		data:JSON.stringify(d),
		dataType:'json',
		complete: moduleChange
	});
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

function moduleChange(data) {
	getLocal();
}

function connectInstallStream(clbk) {
	var evtSource = new EventSource("/installstream");
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
	logInstallStream()
}
