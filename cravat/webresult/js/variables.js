var gridObjs;
var $grids;
var columnGroupPrefix = 'columngroup_';
var columnGroups = null;
var columns = null;
var columnnos = null;
var selectedRowIds = {};
var selectedRowNos = {};
var jobId = null;
var currentTab = null;
var ascendingSort = {};
var dataLengths = {};
var datas = {};
var resultLevels = null;
var jobInfo = null;
var ARBITRARY_HEIGHT_SUBTRACTION = 10;

var prefixLoadDiv = 'load_innerdiv_';

var onemut = null;

var infomgr = new InfoMgr();

var jobDataLoadingDiv = null;

var widgetGenerators = {};

var widgetTableBorderStyle = '1px solid gray';

var detailWidgetOrder = {};

var widgetGridSize = 10;

var dbPath = null;

var filterJson = {};
var filterSet = [];
var filterCols = null;
var filterArmed = {};

var resetTab = {};

var spinner = null;

var shouldResizeScreen = {};

var NUMVAR_LIMIT = 100000;

var firstLoad = true;

var flagNotifyToUseFilter = false;
var missingWidgets = {};

var confPath = null;

var tableSettings = {};
var loadedTableSettings = {};
var viewerWidgetSettings = {};
var loadedViewerWidgetSettings = {};
var heightSettings = {};
var loadedHeightSettings = {};
var defaultSaveName = 'default';
var lastUsedLayoutName = 'default';
var savedLayoutNames = null;
var autoSaveLayout = true;
var windowWidth = 0;
var windowHeight = 0;

// Below is temporary. Implement on aggregator and delete it later.
var soDic = {
    '2kb downstream':'2KD',
    '2kb upstream':'2KU',
    '3-prime utr':'UT3',
    '5-prime utr':'UT5', 
    'intron':'INT', 
    'unknown':'UNK', 
    'synonymous':'SYN', 
    'missense':'MIS', 
    'complex substitution':'CSS', 
    'inframe deletion':'IDV', 
    'inframe insertion':'IIV', 
    'stop lost':'STL', 
    'splice site':'SPL', 
    'stop gained':'STG', 
    'frameshift deletion by 2':'FD2', 
    'frameshift deletion by 1':'FD1', 
    'frameshift insertion by 2':'FI2', 
    'frameshift insertion by 1':'FI1', 
    '':''
};
