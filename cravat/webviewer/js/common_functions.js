//This class is used to define static common functions that are used all over the code
function Commons(){}
//Variables
//===========================================================================================================================================================================
//Number of pixels given to each letter
Commons.PIXELS_PER_LETTER = 13;
//NUMBER OF HUMAN GENES
Commons.NUMBER_HUMAN_GENES = 20000;

Commons.soColors = {
	"light": {
		"SYN": "rgb(190, 190, 190)",
		"MIS": "rgb(255, 251, 123)",
		"CSS": "rgb(141, 237, 255)",
		"IIV": "rgb(181, 255, 131)",
		"IDV": "rgb(49, 191, 49)",
		"STL": "rgb(63, 255, 193)",
		"SPL": "rgb(255, 118, 35)",
		"STG": "rgb(250, 0, 0)",
		"FI1": "rgb(255, 0, 221)",
		"FI2": "rgb(255, 0, 221)",
		"FD1": "rgb(200, 0, 255)",
		"FD2": "rgb(200, 0, 255)",
		"INT": "rgb(190, 130, 150)",
		"UT5": "rgb(255, 251, 123)",
		"UT3": "rgb(141, 237, 255)",
		"2KU": "rgb(181, 255, 131)",
		"2KD": "rgb(49, 191, 49)"
	}, 
	"dark": {
		"SYN": "rgb(168, 168, 168)",
		"MIS": "rgb(197, 191, 0)",
		"CSS": "rgb(125, 210, 226)",
		"IIV": "rgb(153, 216, 110)",
		"IDV": "rgb(34, 139, 34)",
		"STL": "rgb(52, 214, 162)",
		"SPL": "rgb(218, 100, 28)",
		"STG": "rgb(216, 1, 1)",
		"FI1": "rgb(195, 1, 169)",
		"FI2": "rgb(195, 1, 169)",
		"FD1": "rgb(163, 0, 208)",							
		"FD2": "rgb(163, 0, 208)",							
		"INT": "rgb(168, 100, 130)",
		"UT5": "rgb(197, 191, 0)",
		"UT3": "rgb(125, 210, 226)",
		"2KU": "rgb(153, 216, 110)",
		"2KD": "rgb(34, 139, 34)",
	}
};

Commons.soDic = {'FI':'Frameshift ins', 
	     'FD1':'Frameshift del 1',
	     'FD2':'Frameshift del 2',
	     'FI1':'Frameshift ins 1',
	     'FI2':'Frameshift ins 2',
	     'IIV':'Inframe ins',
	     'IDV':'Inframe del',
	     'MIS':'Missense',
	     'STG':'Stopgain',
	     'STL':'Stoploss',
	     'SPL':'Splice site',
	     'SYN':'Synonymous',
	     'CSS':'Complex sub',
	     'UNK':'Unknown',
	     'INT':'Intron',
	     'UT5':'5" UTR',
	     'UT3':'3" UTR',
	     '2KU':'2k upstream',
	     '2KD':'2k downstream'
};
Commons.soDicOpp = {'Frameshift ins':'FI', 
		'Frameshift del 1':'FD1',
		'Frameshift del 2':'FD2',
		'Frameshift ins 1':'FI1',
		'Frameshift ins 2':'FI2',
		'Inframe ins':'IIV',
		'Inframe del':'IDV',
		'Missense' :'MIS',
		'Stopgain':'STG',
		'Stoploss':'STL',
		'Splice site':'SPL',
		'Synonymous':'SYN',
		'Complex sub':'CSS',
		'Unknown':'UNK',
		'Intron':'INT',
		'5" UTR':'UT5',
		'3" UTR':'UT3',
		'2k upstream':'2KU',
		'2k downstream':'2KD'
};

Commons.specialSoChanges = {
		"Frameshft ins 1": "Frmshft ins 1",
		"Frameshft ins 2": "Frmshft ins 2",
		"Frameshft del 1": "Frmshft del 1",
		"Frameshft del 2": "Frmshft del 2",
};

//Functions
//===========================================================================================================================================================================

Commons.fillWithLoadingMessage = function(div, message){
	var loadingSpan = getEl('span');
	loadingSpan.classList.add("loadingspan");
	addEl(loadingSpan, getTn(message));
	addEl(div, loadingSpan);
};

//This static function cleans up a JSON response allowing it to be parsed correctly
Commons.getCleanedJson  = function(jsonStr) {
	var cleanedJsonStr = null;
	if (jsonStr.indexOf('{') == -1 && jsonStr.indexOf('[') == -1){
		//TODO Maybe have something here
		cleanedJsonStr = jsonStr;
	} else {
		if (jsonStr.indexOf('{') > -1 && jsonStr.indexOf('[') > -1){
			if (jsonStr.indexOf('{') < jsonStr.indexOf('[')){
				cleanedJsonStr = jsonStr.substr(jsonStr.indexOf('{'));
				cleanedJsonStr = cleanedJsonStr.substr(0, cleanedJsonStr.lastIndexOf('}') + 1);
			} else {
				cleanedJsonStr = jsonStr.substr(jsonStr.indexOf('['));
				cleanedJsonStr = cleanedJsonStr.substr(0, cleanedJsonStr.lastIndexOf(']') + 1);
			}
		} else if (jsonStr.indexOf('{') > -1 && jsonStr.indexOf('[') == -1){
			cleanedJsonStr = jsonStr.substr(jsonStr.indexOf('{'));
			cleanedJsonStr = cleanedJsonStr.substr(0, cleanedJsonStr.lastIndexOf('}') + 1);
		} else {
			cleanedJsonStr = jsonStr.substr(jsonStr.indexOf('['));
			cleanedJsonStr = cleanedJsonStr.substr(0, cleanedJsonStr.lastIndexOf(']') + 1);
		}
	}
	return cleanedJsonStr;
};

//Make an asynchronous 'GET' call to the jersey servlet
Commons.asynchGETJerseyServlet = function(methodCalling, data, responseFunction){
	var url = 'rest/service/'+methodCalling+'?';
	for (var dNum=0; dNum<data.length; dNum++){
		if (dNum > 0){
			url += '&';
		}
		url += 'param'+String(dNum+1) + '=' + data[dNum];
	}
	this.asynchGET(url, responseFunction);
};

//Make an asynchronous 'GET' call to the widget servlet
Commons.asynchGETWidgetServlet = function(methodCalling, data, responseFunction){
	var url = 'rest/widgetservice/'+methodCalling+'?';
	for (var dNum=0; dNum<data.length; dNum++){
		if (dNum > 0){
			url += '&';
		}
		url += 'param'+String(dNum+1) + '=' + data[dNum];
	}
	this.asynchGET(url, responseFunction);
};

//Make an aysynchronouse 'GET' call to any URL passed in
Commons.asynchGET = function(url, responseFunction){
	var request = new XMLHttpRequest();
	request.open('GET', url, true);
	request.onload = function(e){
		responseFunction(request.response);
	};
	request.onerror = function(f){
		console.log(f.stack);
	};
	request.send(null);
};

//Make an asynchronous 'POST' call to the widget servlet
Commons.asynchPOSTWidgetServlet = function(methodCalling, data, responseFunction){
	var url = 'rest/widgetservice/'+methodCalling+'?';
	var params = "";
	for (var dNum=0; dNum<data.length; dNum++){
		if (dNum > 0){
			params += '&';
		}
		params += 'param'+String(dNum+1) + '=' + data[dNum];
	}
	this.asynchPOST(url, params, responseFunction);
};

//Make an aysynchronouse 'POST' call to any URL passed in
Commons.asynchPOST = function(url, params, responseFunction){
	var request = new XMLHttpRequest();
	request.open('POST', url, true);
	request.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
	//TODO should you be using 'request.onreadystatechange'
	request.onload = function(e){
		responseFunction(request.response);
	};
	request.onerror = function(f){
		console.log(f.stack);
	};
	request.send(params);
};


//This first checks if the JOSN response is 'error'. 
//If it is not 'error' then the JSON is cleaned and passed back.
Commons.checkCleanParseJSONResponse = function(jsonStr){
	this.checkResponse(jsonStr);
	jsonStr = this.getCleanedJson(jsonStr);
	var jsonObj = JSON.parse(jsonStr);
	return jsonObj;
};

Commons.checkResponse = function(responseStr){
	if (responseStr.toLowerCase() == "error"){
		throw("Data not retrieved.");
	}
};

//Make an error title for the widget
Commons.fillWidgetWithErr = function(widget, errTitleTxt, errContentTxt){
	this.fillDivWithErr(widget, errTitleTxt, errContentTxt, "widget");
};

//Make spans that describe an error and put them in the div passed in
Commons.fillDivWithErr = function(div, errTitleTxt, errContentTxt, areaWithErr){
	//Since you are filling the div with the error, clear the div first
	div.innerHTML = "";
	var errDiv = getEl('div');
		var errTitleDiv = getEl('div');
		errTitleDiv.classList.add(areaWithErr + "ErrTitle");
			var errTitleTxtNode = getTn(errTitleTxt);
			addEl(errTitleDiv, errTitleTxtNode);
		addEl(errDiv, errTitleDiv);
		var errContentsDiv = getEl('div');
		errContentsDiv.classList.add(areaWithErr + "ErrContent");

			var errContentTxtNode = getTn(errContentTxt.stack);
			addEl(errContentsDiv, errContentTxtNode);
		addEl(errDiv, errContentsDiv);
	addEl(div, errDiv);
};

//Build table based on the data passed in
//data must be in the following configuration
//table = {
//		'head':{
//			'cols': [
//				1,2,3
//			]
//		},
//		'body' : [
//		          {
//					'attrs': [
//		             	'name:value'
//		             	],
//		           'cols':[
//						[1,2,3],
//						[1,2,3]
//		           ]
//				}
//		]
//	};
Commons.buildBasicTable = function(data, tableClass){
	var table = getEl('table');
	table.classList.add(tableClass);
	function buildHead(dataH){
		var thead = getEl('thead');
		var tr = getEl('tr');
		addEl(thead, buildRow('th', dataH));
		addEl(thead, tr);
		return thead;
	}
	function buildBody(dataB){
		var tbody = getEl('tbody');
		for (var rNum=0; rNum < dataB.length; rNum++){
			addEl(tbody, buildRow('td', dataB[rNum]));
		}
		return tbody;
	}
	function buildRow(thOrTd, row){
		var tr = getEl('tr');
		if (row.hasOwnProperty('attrs')){
			for (var aNum=0; aNum < row['attrs'].length; aNum++){
				setAttr(tr, row['attrs'][aNum]);
			}
		}
		for (var cNum=0; cNum < row['cols'].length; cNum++){
			addEl(tr, buildColumn(thOrTd, row['cols'][cNum]));
		}
		return tr;
	}
	function buildColumn(thOrTd, txt){
		var col = getEl(thOrTd);
		addEl(col, getTn(txt));
		return col;
	}
	function setAttr(node, attr){
		var attrName = attr.split(":")[0];
		var attrVal = attr.split(":")[1];
		node.setAttribute(attrName, attrVal);
	}
	addEl(table, buildHead(data['head']));
	addEl(table, buildBody(data['body']));
	return table;
};

Commons.buildBasicDropDown = function(types, typeVals, 
		changeFn, chosenType) {
	//Drop down
	var dropDown = getEl('select');
	//Build each option
	function buildOption(txt, value){
		var option = getEl("option");
		option.value = value;
		addEl(option, getTn(txt));
		return option;
	}
	// Initiate building the drop down
	for (var tNum=0; tNum < types.length; tNum++){
		var type = types[tNum];
		var typeVal = typeVals[type];
		var option = buildOption(type, typeVal);
		if (type == chosenType) {
			option.setAttribute('selected', true);
		}
		addEl(dropDown, option);
	}
	dropDown.addEventListener('change', function(){
		changeFn(this.value);
	});
	return dropDown;
};


//This function allows one class to inherit the prototype of the other
//This is same same but different to Java inheritance
//	But actually its a little differen
Commons.inheritsFrom = function (child, parent) {
    child.prototype = Object.create(parent.prototype);
};
