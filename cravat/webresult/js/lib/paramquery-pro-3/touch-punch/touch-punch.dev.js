/*!
 * jQuery UI Touch Punch 3.0.0
 *
 * Copyright 2011–2014, Dave Furfero
 * Dual licensed under the MIT or GPL Version 2 licenses.
 *
 * Depends:
 *  jquery.ui.widget.js
 *  jquery.ui.mouse.js
 */
(function ($) {
  $.support.touch = 'ontouchend' in document;
  if (!$.support.touch) {
    return;
  }
  var mouseProto = $.ui.mouse.prototype,
      _mouseInit = mouseProto._mouseInit,
      firstTap = false,
      secondTap = false,
      _mouseDestroy = mouseProto._mouseDestroy,
      touchHandled;
  function simulateMouseEvent (event, simulatedType, relatedTarget) {
    if (event.originalEvent.touches.length > 1) {
      return;
    }
    event.preventDefault();
    var touch = event.originalEvent.changedTouches[0],
        simulatedEvent = document.createEvent('MouseEvents');
    simulatedEvent.initMouseEvent(
      simulatedType,
      true,
      true,
      window,
      1,
      touch.screenX,
      touch.screenY,
      touch.clientX,
      touch.clientY,
      false,
      false,
      false,
      false,
      0,
      relatedTarget
    );
    event.target.dispatchEvent(simulatedEvent);
  }
  mouseProto._touchStart = function (event) {
    var self = this,
        widgetName = self.widgetName;
    if (touchHandled || self._touchHandled) {
        return;
    }
    var cancel = self.options.cancel,
        touch = event.originalEvent.changedTouches[0],
        target = touch.target,
        isCancel = (typeof cancel === "string" && target && target.nodeName ?
            $(target).closest(cancel).length : false);
    if ( isCancel || ( widgetName != 'pqGrid' && !self._mouseCapture(touch) ) ) {
        return;
    }
    self._touchHandled = touchHandled = true;
    if( !firstTap ){
        firstTap = {x: touch.pageX, y:touch.pageY, target: target };
        setTimeout(function(){
            firstTap = false;
        }, 400);
    }
    else if( target && target == firstTap.target){
        var x = firstTap.x - touch.pageX,
            y = firstTap.y - touch.pageY,
            dist = Math.sqrt( x*x + y*y );
        if( dist <= 12 ){
            secondTap = true;
            setTimeout(function(){
                secondTap = false;
            }, 200);
        }
    }
    self._touchMoved = false;
    simulateMouseEvent(event, 'mouseover');
    simulateMouseEvent(event, 'mousemove');
    simulateMouseEvent(event, 'mousedown');
  };
  mouseProto._touchMove = function (event) {
    if ( !this._touchHandled ) {
      return;
    }
    this._touchMoved = true;
    simulateMouseEvent(event, 'mousemove');
  };
  mouseProto._touchEnd = function (event) {
    if ( !this._touchHandled ) {
      return;
    }
    simulateMouseEvent(event, 'mouseup');
    simulateMouseEvent(event, 'mouseout');
    if (!this._touchMoved) {
      simulateMouseEvent(event, 'click');
    }
    this._touchMoved = false;
    this._touchHandled = false;
    touchHandled = false;
    if(secondTap){
        simulateMouseEvent(event, 'dblclick');
    }
  };
  mouseProto._mouseInit = function () {
    var self = this,
        EN = this.eventNamespace;
    var obj = {};
    obj['touchstart'+EN] = $.proxy(self, '_touchStart');
    obj['touchmove'+EN] = $.proxy(self, '_touchMove');
    obj['touchend'+EN] = $.proxy(self, '_touchEnd');
    self.element.bind(obj);
    _mouseInit.call(self);
  };
  mouseProto._mouseDestroy = function () {
    var self = this,
        element = self.element,
        EN = this.eventNamespace;
    if ( this._touchHandled) {
        touchHandled = false;
        this._touchHandled = false;
    }
    element.unbind( 'touchstart' + EN );
    element.unbind( 'touchmove' + EN );
    element.unbind( 'touchend' + EN );
    _mouseDestroy.call(self);
  };
})(jQuery);