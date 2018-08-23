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
var loadedFilterJson = {};

var filterSet = [];

var resetTab = {};

var spinner = null;

var filterCols = null;

var shouldResizeScreen = {};

var NUMVAR_LIMIT = 100000;

var firstLoad = true;

var flagNotifyToUseFilter = false;

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
