function getEl (tag) {
	var div = document.createElement(tag);
	return div;
}

function getTn (text) {
	return document.createTextNode(text);
}

function addEl (parent, child) {
	parent.appendChild(child);
	return parent;
}

function getTrimmedTn (text) {
	var textLengthCutoff = 10;
	var span = getEl('span');
	var tn = getTn(text);
	if (text.length > textLengthCutoff) {
		span.title = text;
		text = text.substring(0, textLengthCutoff) + '...';
		tn.textContent = text;
	}
	addEl(span, tn);
	return span;
}

function getExclamationTd (flag) {
	var td = document.createElement('td');
	td.style.width = 50;
	if (flag == true) {
		var img = new Image();
		img.src = '/result/images/exclamation.png';
		img.width = 14;
		img.height = 14;
		td.appendChild(img);
	}
	return td;
}

function getTextTd (text) {
	var td = document.createElement('td');
	td.style.width = 150;
	td.appendChild(document.createTextNode(text));
	return td;
}

//Function to convert seconds to HH:MM:SS
function toHHMMSS (sec_num) {
    var hours   = Math.floor(sec_num / 3600);
    var minutes = Math.floor((sec_num - (hours * 3600)) / 60);
    var seconds = sec_num - (hours * 3600) - (minutes * 60);

    if (hours   < 10) {hours   = "0"+hours;}
    if (minutes < 10) {minutes = "0"+minutes;}
    if (seconds < 10) {seconds = "0"+seconds;}
    
    return hours+':'+minutes+':'+seconds;
}

function getDetailWidgetDivs (tabName, widgetName, title) {
	var div = document.createElement('fieldset');
	div.id = 'detailwidget_' + tabName + '_' + widgetName;
	div.className = 'detailwidget';
	var width = null;
	var height = null;
	var top = null;
	var left = null;
	if (viewerWidgetSettings['info'] != undefined) {
		for (var i = 0; i < viewerWidgetSettings['info'].length; i++) {
			var setting = viewerWidgetSettings['info'][i];
			if (setting['widgetkey'] == widgetName) {
				width = parseInt(setting['width'].replace('px', ''));
				height = parseInt(setting['height'].replace('px', ''));
				top = setting['top'];
				left = setting['left'];
				break;
			}
		}
	} else {
		width = widgetGenerators[widgetName][tabName]['width'];
		height = widgetGenerators[widgetName][tabName]['height'];
	}
	div.clientWidth = width;
	div.clientHeight = height;
	div.style.width = width + 'px';
	div.style.height = height + 'px';
	if (top) {
		div.style.top = top;
	}
	if (left) {
		div.style.left = left;
	}
	div.setAttribute('widgetkey', widgetName);
	
	// Header
	var header = getEl('div');
	header.className = 'detailwidgetheader';
	addEl(div, header);
	
	// Title
	var titleDiv = getEl('legend');
	titleDiv.className = 'detailwidgettitle';
	titleDiv.style.cursor = 'move';
	addEl(header, addEl(titleDiv, getTn(title)));
	
	// Div for pin and x icons
	var iconDiv = getEl('div');
	iconDiv.className = 'detailwidgeticondiv';
	addEl(header, iconDiv);

	// Pin button
	var pinButton = getEl('img');
	pinButton.src = '/result/images/pin.png';
	pinButton.className = 'detailwidgetpinbutton';
	pinButton.classList.add('unpinned');
	pinButton.setAttribute('widgetname', widgetName);
	pinButton.addEventListener('click', function (evt) {
		onClickWidgetPinButton(evt, tabName);
	});
	addEl(iconDiv, pinButton);

	// Close button
	var closeButton = getEl('img');
	closeButton.src = '/result/images/close-button.png';
	closeButton.className = 'closebutton';
	//closeButton.className = 'detailwidgetclosebutton';
	closeButton.setAttribute('widgetname', widgetName);
	closeButton.addEventListener('click', function (evt) {
		onClickWidgetCloseButton(tabName, evt);
	});
	addEl(iconDiv, closeButton);
	
	var hr = getEl('hr');
    hr.style.margin = '5px';
    hr.style.marginInlineStart = '0px';
    hr.style.marginInlineEnd = '0px';
	addEl(div, hr);
	
	// Content div
	var detailContentDiv = getEl('div');
	detailContentDiv.id = 'widgetcontentdiv_' + widgetName + '_' + tabName;
	detailContentDiv.className = 'detailcontentdiv';
	detailContentDiv.style.height = 'calc(100% - 32px)';
    detailContentDiv.style.padding = '0px';
	addEl(div, detailContentDiv);
	
	return [div, detailContentDiv];
}

function addSpinner(parentDiv, scaleFactor, minDim, spinnerDivId){
	var parentRect = parentDiv.getBoundingClientRect();
	var scaleDim = Math.floor(scaleFactor * Math.min(parentRect.width, parentRect.height));
	var spinnerDim = Math.max(scaleDim, minDim);
	var spinnerDiv = getEl('div');
	spinnerDiv.id = spinnerDivId;
	spinnerDiv.style.position = 'absolute';
	spinnerDiv.style.textAlign = 'center';
	var spinnerImg = getEl('img');
	spinnerImg.src = "/result/images/bigSpinner.gif";
	spinnerImg.style.width = spinnerDim + 'px';
	spinnerImg.style.height = spinnerDim + 'px';
	addEl(spinnerDiv, spinnerImg);
	addEl(parentDiv, spinnerDiv);
	var spinnerRect = spinnerDiv.getBoundingClientRect();
	
	spinnerDiv.style.top = parentRect.top + parentRect.height/2 - spinnerRect.height/2;
	spinnerDiv.style.left = parentRect.left + parentRect.width/2 - spinnerRect.width/2;
	return spinnerDiv;
}

function addSpinnerById(parentDivId, scaleFactor, minDim, spinnerDivId){
	var parentDiv = document.getElementById(parentDivId);
	var spinnerDiv = addSpinner(parentDiv, scaleFactor, minDim, spinnerDivId);
	return spinnerDiv;
}

function saveFilterSetting (name, useFilterJson) {
	var saveData = {};
    if (useFilterJson == undefined) {
        makeFilterJson();
    }
	saveData['filterSet'] = filterJson;
	var saveDataStr = JSON.stringify(saveData);
	$.ajax({
        type: 'GET',
        async: 'false',
        url: '/result/service/savefiltersetting', 
        data: {'dbpath': dbPath, name: name, 'savedata': saveDataStr},
        success: function (response) {
            writeLogDiv('Filter setting has been saved.');
        }
    });
}

function deleteFilterSetting (name) {
	$.get('/result/service/deletefiltersetting', {'dbpath': dbPath, name: name}).done(function (response) {
        if (response == 'deleted') {
            writeLogDiv('Filter setting has been deleted.');
        } else {
            alert(response);
        }
    });
}

function saveFilterSettingAs () {
	$.get('/result/service/getfiltersavenames', {'dbpath': dbPath}).done(function (response) {
		var names = '' + response;
		var msg = 'Please enter layout name to save.';
		if (names != '') {
			msg = msg + ' Saved layout names are: ' + names;
		}
        if (lastUsedLayoutName == defaultSaveName) {
            lastUsedLayoutName = '';
        }
		var name = prompt(msg, lastUsedLayoutName);
		if (name != null) {
			saveFilterSetting(name);
		}
	});
}

function deleteFilterSettingAs () {
	$.get('/result/service/getfiltersavenames', {'dbpath': dbPath}).done(function (response) {
		var names = '' + response;
		var msg = 'Please enter layout name to delete.';
		if (names != '') {
			msg = msg + ' Saved layout names are: ' + names;
		}
		var name = prompt(msg, lastUsedLayoutName);
		if (name != null) {
			deleteFilterSetting(name);
		}
	});
}

function saveLayoutSettingAs () {
	$.get('/result/service/getlayoutsavenames', {'dbpath': dbPath}).done(function (response) {
		var names = '' + response;
		var msg = 'Please enter layout name to save.';
		if (names != '') {
			msg = msg + ' Saved layout names are: ' + names;
		}
        if (lastUsedLayoutName == defaultSaveName) {
            lastUsedLayoutName = '';
        }
		var name = prompt(msg, lastUsedLayoutName);
		if (name != null) {
			saveLayoutSetting(name);
		}
	});
}

function saveWidgetSetting (name) {
	var saveData = {};
	saveData['widgetSettings'] = {};
	var widgets = {};
	var detailContainerDiv = document.getElementById('detailcontainerdiv_variant');
	if (detailContainerDiv != null) {
		saveData['widgetSettings']['variant'] = [];
		widgets = $(detailContainerDiv).packery('getItemElements');
		for (var i = 0; i < widgets.length; i++) {
			var widget = widgets[i];
			saveData['widgetSettings']['variant'].push(
					{'id': widget.id,
					'widgetkey': widget.getAttribute('widgetkey'),
					'top': widget.style.top, 
					'left': widget.style.left, 
					'width': widget.style.width, 
					'height': widget.style.height});
		};
	}
	var detailContainerDiv = document.getElementById('detailcontainerdiv_gene');
	if (detailContainerDiv != null) {
		saveData['widgetSettings']['gene'] = [];
		widgets = $(detailContainerDiv).packery('getItemElements');
		for (var i = 0; i < widgets.length; i++) {
			var widget = widgets[i];
			saveData['widgetSettings']['gene'].push(
					{'id': widget.id,
					'widgetkey': widget.getAttribute('widgetkey'),
					'top': widget.style.top, 
					'left': widget.style.left, 
					'width': widget.style.width, 
					'height': widget.style.height});
		};
	}
	var detailContainerDiv = document.getElementById('detailcontainerdiv_info');
	if (detailContainerDiv != null) {
		saveData['widgetSettings']['info'] = [];
		widgets = $(detailContainerDiv).packery('getItemElements');
		for (var i = 0; i < widgets.length; i++) {
			var widget = widgets[i];
			saveData['widgetSettings']['info'].push(
					{'id': widget.id,
					'widgetkey': widget.getAttribute('widgetkey'),
					'top': widget.style.top, 
					'left': widget.style.left, 
					'width': widget.style.width, 
					'height': widget.style.height});
		};
	}
	var saveDataStr = JSON.stringify(saveData);
	$.ajax({
		url: '/result/service/savewidgetsetting', 
		type: 'get',
		async: false,
		data: {'dbpath': dbPath, name: name, 'savedata': saveDataStr},
		success: function (response) {
			writeLogDiv('Widget setting has been saved.');
		}
    });
}

function saveLayoutSetting (name) {
	var saveData = {};
	
	// Table layout
	saveData['tableSettings'] = {};
	if ($grids['variant'] != undefined) {
		var colGroupModel = $grids['variant'].pqGrid('option', 'colModel');
		var data = [];
		for (var i = 0; i < colGroupModel.length; i++) {
			var colGroup = colGroupModel[i];
			var group = {};
			group = {'title': colGroup.title, 'cols': []};
			var cols = colGroup.colModel;
			for (var j = 0; j < cols.length; j++) {
				var col = cols[j];
				group.cols.push({'col': col.col, 'dataIndx': col.dataIndx, 'width': col.width});
			}
			data.push(group);
		}
		saveData['tableSettings']['variant'] = data;
	}
	if ($grids['gene'] != undefined) {
		var colGroupModel = $grids['gene'].pqGrid('option', 'colModel');
		var data = [];
		for (var i = 0; i < colGroupModel.length; i++) {
			var colGroup = colGroupModel[i];
			var group = {};
			group = {'title': colGroup.title, 'cols': []};
			var cols = colGroup.colModel;
			for (var j = 0; j < cols.length; j++) {
				var col = cols[j];
				group.cols.push({'col': col.col, 'dataIndx': col.dataIndx, 'width': col.width});
			}
			data.push(group);
		}
		saveData['tableSettings']['gene'] = data;
	}
	
	// Widget layout
	saveData['widgetSettings'] = {};
	var widgets = {};
	var detailContainerDiv = document.getElementById('detailcontainerdiv_variant');
	if (detailContainerDiv != null) {
		saveData['widgetSettings']['variant'] = [];
		widgets = $(detailContainerDiv).packery('getItemElements');
		for (var i = 0; i < widgets.length; i++) {
			var widget = widgets[i];
			saveData['widgetSettings']['variant'].push(
					{'id': widget.id,
					'widgetkey': widget.getAttribute('widgetkey'),
					'top': widget.style.top, 
					'left': widget.style.left, 
					'width': widget.style.width, 
					'height': widget.style.height});
		};
	}
	var detailContainerDiv = document.getElementById('detailcontainerdiv_gene');
	if (detailContainerDiv != null) {
		saveData['widgetSettings']['gene'] = [];
		widgets = $(detailContainerDiv).packery('getItemElements');
		for (var i = 0; i < widgets.length; i++) {
			var widget = widgets[i];
			saveData['widgetSettings']['gene'].push(
					{'id': widget.id,
					'widgetkey': widget.getAttribute('widgetkey'),
					'top': widget.style.top, 
					'left': widget.style.left, 
					'width': widget.style.width, 
					'height': widget.style.height});
		};
	}
	var detailContainerDiv = document.getElementById('detailcontainerdiv_info');
	if (detailContainerDiv != null) {
		saveData['widgetSettings']['info'] = [];
		widgets = $(detailContainerDiv).packery('getItemElements');
		for (var i = 0; i < widgets.length; i++) {
			var widget = widgets[i];
			saveData['widgetSettings']['info'].push(
					{'id': widget.id,
					'widgetkey': widget.getAttribute('widgetkey'),
					'top': widget.style.top, 
					'left': widget.style.left, 
					'width': widget.style.width, 
					'height': widget.style.height});
		};
	}
	
	// Heights
	saveData['height'] = {};
	var variantTable = document.getElementById('tablediv_variant');
	if (variantTable) {
		saveData['height']['table_variant'] = variantTable.style.height;
	}
	var geneTable = document.getElementById('tablediv_gene');
	if (geneTable) {
		saveData['height']['table_gene'] = geneTable.style.height;
	}
	var variantDetail = document.getElementById('detaildiv_variant');
	if (variantDetail) {
		saveData['height']['detail_variant'] = variantDetail.style.height;
	}
	var geneDetail = document.getElementById('detaildiv_gene');
	if (geneDetail) {
		saveData['height']['detail_gene'] = geneDetail.style.height;
	}
	
	var saveDataStr = JSON.stringify(saveData);
	$.ajax({
		url: '/result/service/savelayoutsetting', 
		type: 'post',
		data: {'dbpath': dbPath, name: name, 'savedata': saveDataStr}, 
		async: false,
		success: function (response) {
			lastUsedLayoutName = name;
			writeLogDiv('Layout setting has been saved.');
		}
    });
}

function areSameFilters (filter1, filter2) {
	var sameFilter = true;
	for (var i = 0; i < filter1.length; i++) {
		var el1 = filter1[i];
		var sameEl = false;
		for (var j = 0; j < filter2.length; j++) {
			var el2 = filter2[j];
			if (el1[0].col == el2[0].col && el1[1] == el2[1] && el1[2] == el2[2] && el1[3] == el2[3]) {
				sameEl = true;
				break;
			}
		}
		if (sameEl == false) {
			sameFilter = false;
			break;
		}
	}
	for (var i = 0; i < filter2.length; i++) {
		var el1 = filter2[i];
		var sameEl = false;
		for (var j = 0; j < filter1.length; j++) {
			var el2 = filter1[j];
			if (el1[0].col == el2[0].col && el1[1] == el2[1] && el1[2] == el2[2] && el1[3] == el2[3]) {
				sameEl = true;
				break;
			}
		}
		if (sameEl == false) {
			sameFilter = false;
			break;
		}
	}
	return sameFilter;
}

function showTab (tabName) {
	$('.tabhead.show').removeClass('show').addClass('hide');
	$('#tabhead_' + tabName).removeClass('hide').addClass('show');
	$('.tabcontent.show').removeClass('show').addClass('hide');
	$('#tab_' + tabName).removeClass('hide').addClass('show');
}

function applyWidgetSetting (level) {
	var settings = viewerWidgetSettings[level];
	if (settings == undefined)  {
		return;
	}
	var outerDiv = document.getElementById('detailcontainerdiv_' + level);
	if (outerDiv == null) {
		return;
	}
	var widgets = outerDiv.children;
	if (widgets.length > 0) {
		var items = Packery.data(outerDiv).items;
		var widgetsInLayout = [];
		var widgetCount = 0;
		for (var i = 0; i < settings.length; i++) {
			var setting = settings[i];
			for (var j = 0; j < items.length; j++) {
				var item = items[j];
				if (item.element.id == setting.id) {
					item.element.style.top = setting['top'];
					item.element.style.left = setting['left'];
					item.element.style.width = setting['width'];
					item.element.style.height = setting['height'];
					var tmp = items[widgetCount];
					items[widgetCount] = item;
					items[j] = tmp;
					widgetCount++;
					break;
				}
			}
		}
		$(outerDiv).packery();
	}
}

function applyTableSetting (level) {
	var settings = tableSettings[level];
	if (settings == undefined) {
		return;
	}
	var $grid = $grids[level];
	var colGroups = $grid.pqGrid('option', 'colModel');
	var newColModel = [];
	for (var i = 0; i < settings.length; i++) {
		var colGroupSetting = settings[i];
		var colGroupColsSetting = colGroupSetting.cols;
		for (var j = 0; j < colGroups.length; j++) {
			var colGroup = colGroups[j];
			if (colGroup.title == colGroupSetting.title) {
				newColModel.push(colGroup);
				newColModel.colModel = [];
				var cols = colGroup.colModel;
				for (k = 0; k < colGroupColsSetting.length; k++) {
					var colSetting = colGroupColsSetting[k];
					for (l = 0; l < cols.length; l++) {
						var col = cols[l];
						if (col.col == colSetting.col) {
							col.width = colSetting.width;
							newColModel.colModel.push(col);
							break;
						}
					}
				}
			}
		}
	}
	$grid.pqGrid('option', 'colModel', newColModel);
	$grid.pqGrid('refresh');
}

function loadFilterSettingAs () {
	$.get('/result/service/getfiltersavenames', {'dbpath': dbPath}).done(function (response) {
		var savedNames = JSON.parse(response.replace(/'/g, '"'));
		var div = document.getElementById('load_filter_select_div');
		$(div).empty();
		div.style.display = 'block';
    	for (var i = 0; i < savedNames.length; i++) {
    		var name = savedNames[i];
    		var a = getEl('a');
    		a.style.cursor = 'pointer';
    		a.style.fontSize = '13px';
    		a.style.fontWeight = 'normal';
    		a.style.width = '100%';
    		a.style.backgroundColor = 'rgb(232, 232, 232)';
    		addEl(a, getTn(name));
    		a.addEventListener('mouseover', function (evt) {
    			evt.target.style.backgroundColor = 'yellow';
    		});
    		a.addEventListener('mouseleave', function (evt) {
    			evt.target.style.backgroundColor = 'white';
    		});
    		a.addEventListener('click', function (evt) {
    			loadFilterSetting(evt.target.textContent, null)
    			div.style.display = 'none';
    		});
    		addEl(div, a);
    		addEl(div, getEl('br'));
    	}
	});
}

function loadFilterSetting (name, callback) {
	$.get('/result/service/loadfiltersetting', {'dbpath': dbPath, 'name': name}).done(function (response) {
		writeLogDiv('Filter setting loaded');
		var data = response;
		filterJson = data['filterSet'];
		var filterWrapDiv = $('#filterwrapdiv');
		filterWrapDiv.empty();
		var filterRootGroupDiv = makeFilterRootGroupDiv(filterJson);
		filterWrapDiv.append(filterRootGroupDiv);
		infomgr.count(dbPath, 'variant', updateLoadMsgDiv);
		if (callback != null) {
			callback();
		}
    });
}

function loadLayoutSettingAs () {
	var div = document.getElementById('load_layout_select_div');
	emptyElement(div);
	$.get('/result/service/getlayoutsavenames', {'dbpath': dbPath}).done(function (response) {
    	var savedLayoutNames = response;
    	for (var i = 0; i < savedLayoutNames.length; i++) {
    		var name = savedLayoutNames[i];
    		var a = getEl('a');
    		a.textContent = name;
    		a.addEventListener('click', function (evt) {
    			loadLayoutSetting(evt.target.textContent, null)
    		});
    		addEl(div, a);
    	}
    });
}

function loadLayoutSetting (name, callback) {
	$.get('/result/service/loadlayoutsetting', {'dbpath': dbPath, 'name': name}).done(function (response) {
		var data = response;
		loadedTableSettings = data['tableSettings'];
		if (loadedTableSettings == undefined) {
			loadedTableSettings = {};
		}
		tableSettings = loadedTableSettings;
		if ((currentTab == 'variant' || currentTab == 'gene') && tableSettings[currentTab] != undefined) {
			applyTableSetting(currentTab);
		}
		loadedViewerWidgetSettings = data['widgetSettings'];
		if (loadedViewerWidgetSettings == undefined) {
			loadedViewerWidgetSettings = {};
		}
		viewerWidgetSettings = loadedViewerWidgetSettings;
		if ((currentTab == 'variant' || currentTab == 'gene' || currentTab == 'info') && viewerWidgetSettings[currentTab] != undefined) {
			applyWidgetSetting(currentTab);
		}
		loadedHeightSettings = data['height'];
		if (loadedHeightSettings == undefined) {
			loadedHeightSettings = {};
		}
		heightSettings = loadedHeightSettings;
		if (callback != null) {
			callback();
		}
		lastUsedLayoutName = name;
		writeLogDiv('Layout setting loaded');
    });
}

function deleteLayoutSettingAs () {
	var div = document.getElementById('delete_layout_select_div');
	emptyElement(div);
	$.get('/result/service/getlayoutsavenames', {'dbpath': dbPath}).done(function (response) {
    	savedLayoutNames = response;
    	for (var i = 0; i < savedLayoutNames.length; i++) {
    		var name = savedLayoutNames[i];
    		var a = getEl('a');
    		a.textContent = name;
    		a.setAttribute('module', name);
    		a.addEventListener('click', function (evt) {
    			var name = evt.target.getAttribute('module');
    			var yes = confirm('Delete ' + name + '?');
    			if (yes) {
    				deleteLayoutSetting(evt.target.textContent, null)
    			}
    		});
    		addEl(div, a);
    	}
    });
}

function deleteLayoutSetting (name, callback) {
	$.get('/result/service/deletelayoutsetting', {'dbpath': dbPath, 'name': name}).done(function (response) {
		writeLogDiv('Layout setting deleted');
    });
}

function renameLayoutSettingAs () {
	var div = document.getElementById('rename_layout_select_div');
	emptyElement(div);
	$.get('/result/service/getlayoutsavenames', {'dbpath': dbPath}).done(function (response) {
    	savedLayoutNames = response;
    	for (var i = 0; i < savedLayoutNames.length; i++) {
    		var name = savedLayoutNames[i];
    		var a = getEl('a');
    		a.textContent = name;
    		a.addEventListener('click', function (evt) {
    			renameLayoutSetting(evt.target.textContent, null)
    		});
    		addEl(div, a);
    	}
    });
}

function renameLayoutSetting (name, callback) {
	var msg = 'Please enter a new name for layout ' + name + '.';
	var newName = prompt(msg, lastUsedLayoutName);
	if (newName != null) {
		$.get('/result/service/renamelayoutsetting', {'dbpath': dbPath, 'name': name, 'newname': newName}).done(function (response) {
			writeLogDiv('Layout name has been changed.');
		});
	}
}

function toggleAutoLayoutSave () {
	var a = document.getElementById('layout_autosave_title');
	var autosave = a.getAttribute('autosave');
	if (autoSaveLayout == false) {
		autoSaveLayout = true;
		a.text = 'V Autosave';
		writeLogDiv('Layout autosave enabled');
	} else {
		autoSaveLayout = false;
		a.text = 'Autosave';
		writeLogDiv('Layout autosave disabled');
	}
}
