(function () {
  'use strict';

  function initColorPicker() {
    var colorField = document.getElementById('id_color');
    if (!colorField) return;

    // Hide the raw text input and replace with a color swatch + picker
    var wrapper = document.createElement('div');
    wrapper.style.cssText = 'display:flex; align-items:center; gap:10px;';

    var swatch = document.createElement('div');
    swatch.style.cssText = 'width:40px; height:40px; border-radius:8px; border:2px solid #e5e7eb; cursor:pointer; background:' + (colorField.value || '#10B981');

    var hexLabel = document.createElement('span');
    hexLabel.style.cssText = 'font-family:monospace; font-size:14px; color:#374151; font-weight:600;';
    hexLabel.textContent = colorField.value || '#10B981';

    // Keep the original input but hide it
    colorField.style.display = 'none';
    colorField.parentNode.appendChild(wrapper);
    wrapper.appendChild(swatch);
    wrapper.appendChild(hexLabel);

    if (typeof Pickr !== 'undefined') {
      var pickr = Pickr.create({
        el: swatch,
        theme: 'classic',
        default: colorField.value || '#10B981',
        swatches: [
          '#10B981', '#3B82F6', '#8B5CF6', '#EC4899',
          '#F59E0B', '#EF4444', '#06B6D4', '#84CC16',
          '#F97316', '#6366F1', '#14B8A6', '#A855F7'
        ],
        components: {
          preview: true,
          opacity: false,
          hue: true,
          interaction: {
            hex: true,
            input: true,
            save: true
          }
        }
      });

      pickr.on('save', function (color) {
        var hex = color.toHEX().toString();
        colorField.value = hex;
        swatch.style.background = hex;
        hexLabel.textContent = hex;
        pickr.hide();
      });

      pickr.on('change', function (color) {
        var hex = color.toHEX().toString();
        swatch.style.background = hex;
        hexLabel.textContent = hex;
      });
    } else {
      // Fallback: click swatch to open native color input
      var nativeInput = document.createElement('input');
      nativeInput.type = 'color';
      nativeInput.value = colorField.value || '#10B981';
      nativeInput.style.cssText = 'position:absolute; opacity:0; width:0; height:0;';
      wrapper.appendChild(nativeInput);

      swatch.addEventListener('click', function () {
        nativeInput.click();
      });

      nativeInput.addEventListener('input', function () {
        colorField.value = this.value;
        swatch.style.background = this.value;
        hexLabel.textContent = this.value;
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initColorPicker);
  } else {
    initColorPicker();
  }

  // Re-init on Django admin inline formset additions
  document.addEventListener('formset:added', initColorPicker);
})();
