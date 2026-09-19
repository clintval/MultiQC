// JavaScript for the fgbio MultiQC module: family size heatmap + stacked bar chart

fgbio_family_data = {};

function load_fgbio_family_data() {
  $(".fgbio_family_size_data").each(function (i, elem) {
    var key_value = JSON.parse(elem.innerHTML);
    fgbio_family_data[key_value[0]] = key_value[1];
  });
}

callAfterDecompressed.push(function (mqc_plotdata) {
  load_fgbio_family_data();

  var fgbio_modules = $(".fgbio_family_size_data").closest(".mqc-module-section");
  fgbio_modules.each(function () {
    var module_element = $(this);
    var module_key = module_element.data("moduleAnchor");
    fgbio_family_size_module(module_element, module_key);
  });
});

function fgbio_family_size_module(module_element, module_key) {
  var s_height = 10;
  var num_samples = 0;
  var sample_names = [];
  var c_width = 0;
  var c_height = 0;
  var ypos = 0;
  var max_fs = 0;
  var current_single_plot = undefined;

  module_element.orig_s_names = {};
  for (var s_name in fgbio_family_data[module_key]) {
    if (Object.prototype.hasOwnProperty.call(fgbio_family_data[module_key], s_name)) {
      module_element.orig_s_names[s_name] = s_name;
    }
  }

  function fgbio_family_size_heatmap() {
    sample_names = [];
    var p_data = {};
    var hidden_samples = 0;
    $.each(fgbio_family_data[module_key], function (s_name, data) {
      var orig_s_name = s_name;
      $.each(window.mqc_rename_f_texts, function (idx, f_text) {
        if (window.mqc_rename_regex_mode) {
          var re = new RegExp(f_text, "g");
          s_name = s_name.replace(re, window.mqc_rename_t_texts[idx]);
        } else {
          s_name = s_name.replace(f_text, window.mqc_rename_t_texts[idx]);
        }
      });
      module_element.orig_s_names[s_name] = orig_s_name;
      p_data[s_name] = JSON.parse(JSON.stringify(data));

      var hide_sample = false;
      for (var i = 0; i < window.mqc_hide_f_texts.length; i++) {
        var f_text = window.mqc_hide_f_texts[i];
        if (window.mqc_hide_regex_mode) {
          if (s_name.match(f_text)) {
            hide_sample = true;
          }
        } else {
          if (s_name.indexOf(f_text) > -1) {
            hide_sample = true;
          }
        }
      }
      if (window.mqc_hide_mode === "show") {
        hide_sample = !hide_sample;
      }
      if (!hide_sample) {
        sample_names.push(s_name);
      } else {
        hidden_samples += 1;
      }
    });
    num_samples = sample_names.length;
    module_element
      .find("#fgbio_family_size_heatmap_div .samples-hidden-warning, #fgbio_family_size_heatmap_div .fgbio-heatmap-no-samples")
      .remove();
    module_element.find("#fgbio_family_size_heatmap_div .hc-plot-wrapper").show();
    if (num_samples === 0) {
      module_element.find("#fgbio_family_size_heatmap_div .hc-plot-wrapper").hide();
      module_element
        .find("#fgbio_family_size_heatmap_div")
        .prepend('<p class="fgbio-heatmap-no-samples text-muted">No samples found.</p>');
    }
    if (hidden_samples > 0) {
      module_element
        .find("#fgbio_family_size_heatmap_div")
        .prepend(
          '<div class="samples-hidden-warning alert alert-warning">' +
            hidden_samples +
            " samples hidden in toolbox.</div>",
        );
    }
    if (num_samples === 0) {
      return;
    }

    c_width = module_element.find("#fgbio_family_size_heatmap").parent().width() - 5;
    c_height = module_element.find("#fgbio_family_size_heatmap").parent().height() - 2;
    s_height = c_height / num_samples;
    if (s_height < 2) {
      s_height = 2;
      c_height = num_samples * 2;
      module_element
        .find("#fgbio_family_size_heatmap")
        .parent()
        .parent()
        .height(c_height + 10);
    }
    module_element.find("#fgbio_family_size_heatmap").prop({
      width: c_width,
      height: c_height + 1,
    });
    var canvas = module_element.find("#fgbio_family_size_heatmap")[0];
    if (canvas && canvas.getContext) {
      var ctx = canvas.getContext("2d");
      ctx.strokeStyle = "#666666";

      max_fs = 0;
      $.each(sample_names, function (idx, s_name) {
        var s = p_data[s_name];
        $.each(s, function (fs, v) {
          fs = parseInt(fs);
          if (fs > max_fs) {
            max_fs = fs;
          }
        });
      });

      // Find global max fraction for color scaling
      var global_max_frac = 0;
      $.each(sample_names, function (idx, s_name) {
        var s = p_data[s_name];
        $.each(s, function (fs, v) {
          var total_frac = v["duplex_frac"] + v["orphan_frac"];
          if (total_frac > global_max_frac) {
            global_max_frac = total_frac;
          }
        });
      });

      ypos = 0;
      $.each(sample_names, function (idx, s_name) {
        // Highlight bar
        var s_col = "#999999";
        $.each(window.mqc_highlight_f_texts, function (idx, f_text) {
          if (
            (window.mqc_highlight_regex_mode && s_name.match(f_text)) ||
            (!window.mqc_highlight_regex_mode && s_name.indexOf(f_text) > -1)
          ) {
            s_col = window.mqc_highlight_f_cols[idx];
          }
        });
        ctx.fillStyle = s_col;
        ctx.fillRect(0, ypos + 1, 5, s_height - 2);

        var s = p_data[s_name];
        var xpos = 6;
        for (var fs = 1; fs <= max_fs; fs++) {
          var this_width = (c_width - 6) / max_fs;
          var total_frac = 0;
          if (s[fs]) {
            total_frac = s[fs]["duplex_frac"] + s[fs]["orphan_frac"];
          }
          // Sequential blue color scale: white (0) to dark navy (max)
          var intensity = global_max_frac > 0 ? total_frac / global_max_frac : 0;
          var r = Math.round(255 - intensity * (255 - 27));
          var g = Math.round(255 - intensity * (255 - 58));
          var b = Math.round(255 - intensity * (255 - 92));
          ctx.fillStyle = "rgb(" + r + "," + g + "," + b + ")";
          ctx.fillRect(xpos, ypos, this_width + 1, s_height);
          xpos += this_width;
        }
        if (num_samples <= 20) {
          ctx.beginPath();
          ctx.moveTo(6, ypos);
          ctx.lineTo(c_width, ypos);
          ctx.stroke();
        }
        ypos += s_height;
      });
      ctx.beginPath();
      ctx.moveTo(6, ypos);
      ctx.lineTo(c_width, ypos);
      ctx.stroke();
    }
  }

  fgbio_family_size_heatmap();

  // Mouseover
  module_element.find("#fgbio_family_size_heatmap").mousemove(function (e) {
    var pos = findPos(this);
    var x = e.pageX - pos.x + 3;
    var y = e.pageY - pos.y;
    var idx = Math.floor(y / s_height);
    var s_name = sample_names[idx];
    var orig_s_name = module_element.orig_s_names[s_name];
    if (s_name === undefined) {
      return false;
    }
    module_element.find("#fgbio_family_size_plot_div .s_name").html(s_name);

    var hover_fs = Math.max(1, Math.ceil(((x - 6) / (c_width - 6)) * max_fs));
    var data = fgbio_family_data[module_key][orig_s_name];
    var thispoint = data[hover_fs];
    if (thispoint) {
      module_element.find("#fgbio_heatmap_key_pos").text(hover_fs);
      module_element
        .find("#fgbio_heatmap_key_duplex span")
        .text((thispoint["duplex_frac"] * 100).toFixed(2) + "%");
      module_element
        .find("#fgbio_heatmap_key_orphan span")
        .text((thispoint["orphan_frac"] * 100).toFixed(2) + "%");
    }
  });

  // Mouseout
  module_element.find("#fgbio_family_size_heatmap").mouseout(function (e) {
    module_element.find("#fgbio_family_size_plot_div .s_name").html("Rollover for sample name");
    module_element.find("#fgbio_heatmap_key_pos").text("-");
    module_element.find("#fgbio_heatmap_key_duplex span").text("-");
    module_element.find("#fgbio_heatmap_key_orphan span").text("-");
  });

  // Click to show stacked bar chart
  module_element.find("#fgbio_family_size_heatmap").click(function (e) {
    e.preventDefault();
    var pos = findPos(this);
    var y = e.pageY - pos.y;
    var idx = Math.floor(y / s_height);
    var s_name = sample_names[idx];
    if (s_name !== undefined) {
      plot_single_family_size(s_name);
    }
  });

  // Prev/next buttons
  module_element.on("click", "." + module_key + "_familysize_single_prevnext", function (e) {
    e.preventDefault();
    var idx = sample_names.indexOf(current_single_plot);
    if ($(this).data("action") === "next") {
      idx++;
    } else {
      idx--;
    }
    if (idx < 0) {
      idx = sample_names.length - 1;
    }
    if (idx >= sample_names.length) {
      idx = 0;
    }
    plot_single_family_size(sample_names[idx]);
  });

  function familySizeSingleClose(e) {
    e.preventDefault();
    module_element.find("#fgbio_family_size_plot_div").slideDown();
    module_element.find("#fgbio_family_size_single_wrapper").slideUp(function () {
      $(this).remove();
    });
  }
  module_element.on("click", "#" + module_key + "_family_size_single_back", familySizeSingleClose);
  $(document).on("mqc_toolbox_open", familySizeSingleClose);

  $(document).on("mqc_highlights mqc_hidesamples mqc_renamesamples mqc_plotresize", function (e) {
    fgbio_family_size_heatmap();
  });
  $(window).resize(function () {
    fgbio_family_size_heatmap();
  });

  function plot_single_family_size(s_name) {
    current_single_plot = s_name;
    var orig_s_name = module_element.orig_s_names[s_name];
    var data = fgbio_family_data[module_key][orig_s_name];

    var family_sizes = Object.keys(data)
      .map(Number)
      .sort(function (a, b) {
        return a - b;
      });
    var duplex_fracs = [];
    var orphan_fracs = [];
    var fs_labels = [];

    for (var i = 0; i < family_sizes.length; i++) {
      var fs = family_sizes[i];
      fs_labels.push(fs.toString());
      duplex_fracs.push(data[fs]["duplex_frac"]);
      orphan_fracs.push(data[fs]["orphan_frac"]);
    }

    // Find peaks
    var duplex_peak_idx = 0;
    var orphan_peak_idx = 0;
    for (var j = 0; j < duplex_fracs.length; j++) {
      if (duplex_fracs[j] > duplex_fracs[duplex_peak_idx]) {
        duplex_peak_idx = j;
      }
      if (orphan_fracs[j] > orphan_fracs[orphan_peak_idx]) {
        orphan_peak_idx = j;
      }
    }

    // Create plot div if needed
    if (module_element.find("#fgbio_family_size_single_wrapper").length === 0) {
      var plot_div = module_element.find("#fgbio_family_size_plot_div");
      plot_div.slideUp();
      var newplot =
        '<div id="fgbio_family_size_single_wrapper">' +
        '<div id="fgbio_family_size_single_controls">' +
        '<button class="btn btn-primary btn-sm" id="' +
        module_key +
        '_family_size_single_back">Back to overview heatmap</button> ' +
        '<div class="btn-group btn-group-sm"> ' +
        '<button class="btn btn-outline-secondary ' +
        module_key +
        '_familysize_single_prevnext" data-action="prev">&laquo; Prev</button> ' +
        '<button class="btn btn-outline-secondary ' +
        module_key +
        '_familysize_single_prevnext" data-action="next">Next &raquo;</button> ' +
        "</div>" +
        "</div>" +
        '<div class="hc-plot-wrapper"><div id="' +
        module_key +
        '_family_size_single" class="hc-plot hc-bar-plot"><small>loading..</small></div></div></div>';
      $(newplot).insertAfter(plot_div).hide().slideDown();
    }

    var target = module_key + "_family_size_single";

    var annotations = [];
    if (duplex_fracs[duplex_peak_idx] > 0) {
      annotations.push({
        x: fs_labels[duplex_peak_idx],
        y: duplex_fracs[duplex_peak_idx] + orphan_fracs[duplex_peak_idx],
        text: "Peak: " + fs_labels[duplex_peak_idx],
        showarrow: true,
        arrowhead: 2,
        ax: 30,
        ay: -30,
        font: { color: "#1b3a5c", size: 11 },
      });
    }
    if (orphan_fracs[orphan_peak_idx] > 0.001) {
      annotations.push({
        x: fs_labels[orphan_peak_idx],
        y: orphan_fracs[orphan_peak_idx],
        text: "Orphan peak: " + fs_labels[orphan_peak_idx],
        showarrow: true,
        arrowhead: 2,
        ax: -30,
        ay: -30,
        font: { color: "#5ec4b5", size: 11 },
      });
    }

    var traces = [
      {
        type: "bar",
        x: fs_labels,
        y: duplex_fracs,
        name: "Duplex SSCS",
        marker: { color: "#1b3a5c" },
        hovertemplate: "Family size %{x}<br>Duplex: %{y:.4f}<extra></extra>",
      },
      {
        type: "bar",
        x: fs_labels,
        y: orphan_fracs,
        name: "Orphaned SSCS",
        marker: { color: "#5ec4b5" },
        hovertemplate: "Family size %{x}<br>Orphan: %{y:.4f}<extra></extra>",
      },
    ];
    var layout = {
      title: s_name,
      barmode: "stack",
      xaxis: {
        title: "Family Size (raw reads per SSCS)",
        type: "category",
      },
      yaxis: {
        title: "Fraction of Total Raw Reads",
        rangemode: "tozero",
      },
      hovermode: "x unified",
      annotations: annotations,
      legend: {
        orientation: "h",
        yanchor: "bottom",
        y: 1.02,
        xanchor: "right",
        x: 1,
      },
    };
    var config = {
      responsive: true,
      displaylogo: false,
      displayModeBar: true,
      toImageButtonOptions: { filename: target },
      modeBarButtonsToRemove: [
        "lasso2d",
        "autoScale2d",
        "pan2d",
        "select2d",
        "zoom2d",
        "zoomIn2d",
        "zoomOut2d",
        "resetScale2d",
        "toImage",
      ],
    };
    Plotly.newPlot(target, traces, layout, config);
  }
}

function findPos(obj) {
  var curleft = 0,
    curtop = 0;
  if (obj.offsetParent) {
    do {
      curleft += obj.offsetLeft;
      curtop += obj.offsetTop;
    } while ((obj = obj.offsetParent));
    return { x: curleft, y: curtop };
  }
  return undefined;
}
