var gridObjs;
var $grids;
var h_runfilters = null;
var columnGroupPrefix = 'columngroup_';
var columnClassPrefix = 'hiddencolumn';
var columnGroups;
var columns;
var columnnos;
var mupitUrls = {};
var grayedColor = 'rgba(150,150,150,100)';
var redColor = 'rgba(255,0,0,200)';
var pvalueCutoffForRed = 0.05;
var scoreCutoffForRed = 0.7;
var gaugeDivSize = 80;
var strokeWidth = 3;
var sliderCutoffs = {
		'vest_best_pvalue': 1.0, 
		'chasm_best_pvalue': 1.0, 
		'allele_frequency': 1.0, 
		'vest_composite_pvalue': 1.0,
		'chasm_composite_pvalue': 1.0};
var selectedRowId = null;
var leftdivExpandedWidth = '200px';
var leftdivCollapsedWidth = '20px';
var jobId = null;
var currentTab = null;
var ascendingSort = {};
var dataLengths = {};
var datas = {};
var filteredResult = false;
var filteredResultMessage = '';
var variantsInGene = null;
var resultLevels = null;
var jsonResponseDatas = null;
var jobInfo = null;
var mappabilityDic = {
		'A75': 'The hg38 reference genome has more than 1 ' +
			   'location with the 75 mer sequence from the query position',
		'ACR': 'ACRO1 (Human acromeric satellite)',
		'ALC': 'ALR/Alpha',
		'BSR': 'Beta satellite repeat/beta',
		'CAT': '(CATTC)n',
		'CHM': 'Chromosome M',
		'CNR': 'Centromeric Repeat',
		'GAA': '(GAATG)n',
		'GAG': '(GAGTG)n',
		'HMI': 'High artifact island',
		'LMI': 'Low artifact island',
		'LSU': 'Large subunit rRNA Hsa',
		'snR': 'Small nuclear RNA',
		'SSU': 'Small subunit rRNA Hsa',
		'STL': 'Satellite repeat',
		'TAR': 'TAR1',
		'TII': 'HSATII (Human satellite II DNA)',
		'TLM': 'Telomeric repeat'};

//These were extracted from the following website:
//	https://wiki.nci.nih.gov/display/TCGA/TCGA+MAF+Files
var tissueTypesDic = {
		'ACC': 'Adrenocortical carcinoma',
		'BLCA': 'Bladder Urothelial Carcinoma',
		'BRCA': 'Breast invasive carcinoma',
		'CESC': 'Cervical squamous cell carcinoma and endocervical adenocarcinoma',
		'CHOL': 'Cholangiocarcinoma',
		'COAD': 'Colon adenocarcinoma',
		'DLBC': 'Lymphoid Neoplasm Diffuse Large B-cell Lymphoma',
		'ESCA': 'Esophageal carcinoma',
		'FPPP': 'FFPE Pilot Phase II',
		'GBM': 'Glioblastoma multiforme',
		'HNSC': 'Head and Neck squamous cell carcinoma',
		'KICH': 'Kidney Chromophobe',
		'KIRC': 'Kidney renal clear cell carcinomav',
		'KIRP': 'Kidney renal papillary cell carcinoma',
		'LAML': 'Acute Myeloid Leukemia',
		'LGG': 'Brain Lower Grade Glioma',
		'LIHC': 'Liver hepatocellular carcinoma',
		'LUAD': 'Lung adenocarcinoma',
		'LUSC': 'Lung squamous cell carcinoma',
		'MESO': 'Mesothelioma',
		'OV': 'Ovarian serous cystadenocarcinoma',
		'PAAD': 'Pancreatic adenocarcinoma',
		'PCPG': 'Pheochromocytoma and Paraganglioma',
		'PRAD': 'Prostate adenocarcinoma',
		'READ': 'Rectum adenocarcinoma',
		'SARC': 'Sarcoma',
		'SKCM': 'Skin Cutaneous Melanoma',
		'STAD': 'Stomach adenocarcinoma',
		'TGCT': 'Testicular Germ Cell Tumors',
		'THCA': 'Thyroid carcinoma',
		'THYM': 'Thymoma',
		'UCEC': 'Uterine Corpus Endometrial Carcinoma',
		'UCS': 'Uterine Carcinosarcoma',
		'UVM': 'Uveal Melanoma'
		};

var ARBITRARY_HEIGHT_SUBTRACTION = 10;

var kgCols = ['kg'];
var espCols = ['esp_af', 'esp_ea', 'esp_aa'];
var exacCols = ['exac_total', 'exac_lat', 'exac_eas', 'exac_oth', 'exac_fin', 
                'exac_sas', 'exac_nfe', 'exac_afr'];
var afDic = {
		'kg':'Total', 
		'esp_avg':'Average', 
		'esp_ea':'European American', 
		'esp_aa':'African American', 
		'exac_total':'Total', 
		'exac_lat':'Latino', 
		'exac_eas':'Eastern Asian', 
		'exac_oth':'Other', 
		'exac_fin':'Finnish', 
		'exac_sas':'South Asian', 
		'exac_nfe':'Non-Finnish European', 
		'exac_afr':'African'};

var tabNameToLevelCoding = {
		'variant': ['variant', 'true'],
		'gene': ['gene', 'true'],
		'noncoding': ['noncoding', 'false'],
		'error': ['error', 'false'],
		'summary': ['summary', 'false']
};

var prefixLoadFieldSetDiv = 'load_fieldset_';
var prefixLoadDiv = 'load_innerdiv_';
var prefixSelectorsDiv = prefixLoadDiv + 'selectors_';
var loadFilterOpenLeftDivWidth = 500;
var loadFilterCloseLeftDivWidth = 200;
var gapBetweenLeftAndRightDivs = 30;

var onemut = null;

var infomgr = new InfoMgr();

var singlepage = false;

var ndexSingle = null;

var cytoscape_instance = null;

var jobDataLoadingDiv = null;

var jobId = null;

var widgetGenerators = {};

var widgetTableBorderStyle = '1px solid gray';

var detailWidgetOrder = {};

var widgetGridSize = 10;

var dbPath = null;

var widgetCharts = {};

var stylesheet = null;
var detaildivRule = null;

var filterJson = {};
var loadedFilterJson = {};

var filterSet = [];

var resetTab = {};

var spinner = null;

var filterCols = null;

var shouldResizeScreen = {};

var NUMVAR_LIMIT = 5000;

var firstLoad = true;

var flagNotifyToUseFilter = false;

var confPath = null;

var tableSettings = {};
var loadedTableSettings = {};
var viewerWidgetSettings = {};
var loadedViewerWidgetSettings = {};

var defaultSaveName = 'default';
var lastUsedLayoutName = 'default';
var savedLayoutNames = null;