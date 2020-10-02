var gridObjs;
var $grids;
var columnGroupPrefix = 'columngroup_';
var columnGroups = null;
var columns = null;
var columnnos = null;
var selectedRowIds = {};
var selectedRowNos = {};
var username = null;
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

var widgetInfo = null;
var detailWidgetOrder = {};

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
var quickSaveName = 'quicksave-name-internal-use';
var lastUsedLayoutName = '';
var savedLayoutNames = null;
var autoSaveLayout = true;
var windowWidth = 0;
var windowHeight = 0;

var tableDetailDivSizes = {};

var showcaseWidgets = {'info': ['sosamplesummary', 'ndexchasmplussummary', 'ndexvestsummary', 'sosummary', 'gosummary', 'circossummary'], 'variant': ['base'], 'gene': ['base']};

var geneRows = {};
var colgroupkeysWithMissingCols = [];

var separateSample = false;

var allSamples = [];
var smartFilters = {};
var showFilterTabContent = false;

var lastUsedFilterName = null;
