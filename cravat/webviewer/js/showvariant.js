function getWidgetTableFrame (columnWidths) {
	var table = getEl('table');
	table.style.fontSize = '12px';
	table.style.borderSpacing = '0px';
	table.style.borderCollapse = 'collapse';
	table.style.borderTop = widgetTableBorderStyle;
	table.style.borderBottom = widgetTableBorderStyle;
	table.style.tableLayout = 'fixed';
	table.style.width = 'calc(100% - 0px)';
	table.setAttribute('columnwidths', columnWidths);
	return table;
}

function getWidgetTableHead (headers) {
	var thead = getEl('thead');
	thead.style.textAlign = 'left';
	thead.style.borderBottom = widgetTableBorderStyle;
	var tr = getEl('tr');
	var numBorder = headers.length - 1;
	for (var i = 0; i < headers.length; i++) {
		var th = getEl('th');
		if (i < numBorder) {
			th.style.borderRight = widgetTableBorderStyle;
		}
		addEl(th, getTn(headers[i]));
		addEl(tr, th);
	}
	addEl(thead, tr);
	return thead;
}

function getWidgetTableTr (values) {
	var numBorder = values.length - 1;
	var tr = getEl('tr');
	tr.style.borderBottom = '1px solid #cccccc';
	for (var i = 0; i < values.length; i++) {
		var td = getEl('td');
		var p = getEl('p');
		p.style.wordWrap = 'break-word';
		if (i < numBorder) {
			td.style.borderRight = widgetTableBorderStyle;
		}
		var value = values[i];
		if (value == null) {
			value = '';
		}
		addEl(td, addEl(p, getTn(value)));
		addEl(tr, td);
	}
	return tr;
}

function getLineHeader (header) {
	var spanHeader = document.createElement('span');
	spanHeader.style.fontWeight = 'bold';
	spanHeader.appendChild(document.createTextNode('  ' + header + ': '));
	return spanHeader;
}

function addInfoLine (div, row, header, col, tabName) {
	addEl(div, getLineHeader(header));
	var text = infomgr.getRowValue(tabName, row, col);
	var spanText = document.createElement('span');
	if (text == undefined || text == null) {
		text = '';
	} else {
		var textLengthCutoff = 20;
		if (text.length > textLengthCutoff) {
			spanText.title = text;
			text = text.substring(0, textLengthCutoff) + '...';
		}
	}
	addEl(spanText, getTn(text));
	addEl(div, spanText);
	addEl(div, getEl('br'));
}

function addInfoLineText (div, header, text) {
	addEl(div, getLineHeader(header));
	var spanText = document.createElement('span');
	if (text == undefined || text == null) {
		text = '';
	} else {
		var textLengthCutoff = 16;
		if (text.length > textLengthCutoff) {
			spanText.title = text;
			text = text.substring(0, textLengthCutoff) + '...';
		}
	}
	addEl(spanText, getTn(text));
	addEl(div, spanText);
	addEl(div, getEl('br'));
}

function addInfoLineLink (div, header, text, link, trimlen) {
	addEl(div, getLineHeader(header));
	var spanText = null;
	if (link == undefined || link == null) {
		text = '';
		spanText = document.createElement('span');
	} else {
		spanText = document.createElement('a');
		spanText.href = link;
		spanText.target = '_blank';
		if (trimlen > 0) {
			if (text.length > trimlen) {
				spanText.title = text;
				text = text.substring(0, trimlen) + '...';
			}
		}
	}
	addEl(spanText, getTn(text));
	addEl(div, spanText);
	addEl(div, getEl('br'));
}

function addBarComponent (outerDiv, row, header, col, tabName) {
	var cutoff = 0.01;
	var barStyle = {
		"top": 0,
		"height": lineHeight,
		"width": 1,
		"fill": 'black',
		"stroke": 'black',
		"round_edge": 1
	};

	// Value
	var value = infomgr.getRowValue(tabName, row, col);
	if (value == null) {
		value = '';
	} else {
		value = value.toFixed(3);
	}
	
	// Div
	var div = getEl('div');
	div.style.display = 'inline-block';
	div.style.margin = '2px';

	// Header
	addEl(div, addEl(getEl('span'), getTn(header + ': ')));
	addEl(div, addEl(getEl('span'), getTn(value)));
	addEl(div, getEl('br'));
	
	// Paper
	var barWidth = 108;
	var barHeight = 12;
	var lineOverhang = 3;
	var lineHeight = barHeight + (2 * lineOverhang);
	var paperHeight = lineHeight + 4;
	var subDiv = document.createElement('div');
	addEl(div, subDiv);
	subDiv.style.width = (barWidth + 10) + 'px';
	subDiv.style.height = paperHeight + 'px';
	var allele_frequencies_map_config = {};
	var paper = Raphael(subDiv, barWidth, paperHeight);
	
	// Box. Red color maxes at 0.3.
	var box = paper.rect(0, lineOverhang, barWidth, barHeight, 4);
	var c = null;
	if (value != '') {
		c = (1.0 - Math.min(1.0, value / 0.3)) * 255;
	} else {
		c = 255;
	}
	box.attr('fill', 'rgb(255, ' + c + ', ' + c + ')');
	box.attr('stroke', 'black');
	
	// Bar
	if (value != '') {
		var bar = paper.rect(value * barWidth, 0, 1, lineHeight, 1);
		bar.attr('fill', 'black');
		bar.attr('stroke', 'black');
	}
	
	addEl(outerDiv, div);
}

function showVariantDetail (row, tabName) {
	if (row == undefined) {
		return;
	}
	
	var detailDiv = document.getElementById('detaildiv_' + tabName);
	if (! detailDiv) {
		return;
	}
	var outerDiv = detailDiv.getElementsByClassName('detailcontainerdiv')[0];
	$outerDiv = $(outerDiv);

	// Remembers widget layout.
	var widgetDivs = outerDiv.children;
	var reuseWidgets = true;
	if (widgetDivs.length == 0) {
		reuseWidgets = false;
	} else {
		widgetDivs = $(outerDiv).packery('getItemElements');
	}
	if (reuseWidgets == true) {
		detailWidgetOrder[tabName] = {};
		for (var i = 0; i < widgetDivs.length; i++) {
			var widgetDiv = widgetDivs[i];
			var widgetKey = widgetDiv.getAttribute('widgetkey');
			detailWidgetOrder[tabName][i] = widgetKey;
			widgetGenerators[widgetKey]['width'] = widgetDiv.clientWidth - 10;
			widgetGenerators[widgetKey]['height'] = widgetDiv.clientHeight - 10;
			widgetGenerators[widgetKey]['top'] = widgetDiv.style.top;
			widgetGenerators[widgetKey]['left'] = widgetDiv.style.left;
		}
	}

	if (tabName == 'error'){
		return
	}
	
	var scrollTop = outerDiv.scrollTop;
		
	var orderNums = Object.keys(detailWidgetOrder[tabName]);
	for (var i = 0; i < orderNums.length; i++) {
		var colGroupKey = detailWidgetOrder[tabName][orderNums[i]];
		if (widgetGenerators[colGroupKey] == undefined) {
			continue;
		}
		var colGroupTitle = infomgr.colgroupkeytotitle[colGroupKey];
		if (colGroupTitle == undefined) {
			colGroupTitle = widgetGenerators[colGroupKey]['name'];
		}
		/*
		if (colGroupKey != 'base' && colGroupKey != 'grasp') {
			continue;
		}
		*/
		if (widgetGenerators[colGroupKey][tabName] != undefined && 
			widgetGenerators[colGroupKey][tabName]['function'] != undefined) {
			var generator = widgetGenerators[colGroupKey][tabName];
			var widgetDiv = null;
			var detailContentDiv = null;
			if (reuseWidgets) {
				widgetContentDiv = document.getElementById(
					'widgetcontentdiv_' + colGroupKey + '_' + tabName);
				if (generator['donterase'] != true) {
					$(widgetContentDiv).empty();
				}
				generator['function'](widgetContentDiv, row, tabName);
			} else {
				[widgetDiv, widgetContentDiv] = 
					getDetailWidgetDivs(tabName, colGroupKey, colGroupTitle);
				generator['function'](widgetContentDiv, row, tabName);
				widgetDiv.style.width = generator['width'] + 'px';
				widgetDiv.style.height = generator['height'] + 'px';
				addEl(outerDiv, widgetDiv);
			}
		}
	}
	if (reuseWidgets == false) {
		$outerDiv.packery({
			columnWidth: widgetGridSize,
			rowHeight: widgetGridSize
		});
		var $widgets = $($outerDiv.packery('getItemElements'));
		$widgets.draggable({
			grid: [widgetGridSize, widgetGridSize],
			handle: '.detailwidgettitle',
		}).resizable({
			grid: [widgetGridSize, widgetGridSize]
		});
		$outerDiv.packery('bindUIDraggableEvents', $widgets);
		var resizeTimeout;
		$widgets.on('resize', function (evt, ui) {
			//adjustWidgetTables(evt.target);
			if (resizeTimeout) {
				clearTimeout(resizeTimeout);
			}
			resizeTimeout = setTimeout(function () {
				$outerDiv.packery('fit', ui.element[0]);
			}, 100);
		});
		$outerDiv.on('layoutComplete', onLayoutComplete);
	}
}


function onLayoutComplete () {
	for (var i = 0; i < viewerWidgetSettings.length; i++) {
		var setting = viewerWidgetSettings[i];
		var el = document.getElementById(setting.id);
		if (el) {
			el.style.top = setting.top;
			el.style.left = setting.left;
			el.style.width = setting.width;
			el.style.height = setting.height;
			viewerWidgetSettings.splice(i, 1);
			i--;
		}
	}
}