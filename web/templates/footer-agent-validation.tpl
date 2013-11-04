    </div> <!-- /container -->

    <!-- Le javascript
    ================================================== -->
    <!-- Placed at the end of the document so the pages load faster -->
    <script src="/public/bootstrap/js/bootstrap-transition.js"></script>
    <script src="/public/bootstrap/js/bootstrap-alert.js"></script>
    <script src="/public/bootstrap/js/bootstrap-modal.js"></script>
    <script src="/public/bootstrap/js/bootstrap-dropdown.js"></script>
    <script src="/public/bootstrap/js/bootstrap-scrollspy.js"></script>
    <script src="/public/bootstrap/js/bootstrap-tab.js"></script>
    <script src="/public/bootstrap/js/bootstrap-tooltip.js"></script>
    <script src="/public/bootstrap/js/bootstrap-popover.js"></script>
    <script src="/public/bootstrap/js/bootstrap-button.js"></script>
    <script src="/public/bootstrap/js/bootstrap-collapse.js"></script>
    <script src="/public/bootstrap/js/bootstrap-carousel.js"></script>
    <script src="/public/bootstrap/js/bootstrap-typeahead.js"></script>
    
  <script src="/public/js/jquery.validate.min.js"></script>
  <script src="/public/js/additional-methods.min.js"></script>
  <script>
  $.validator.addMethod(
        "regex",
        function(value, element, regexp) {
            var re = new RegExp(regexp);
            return this.optional(element) || re.test(value);
        },
        "Please check your input."
);
  </script>

<script>
$(document).ready(function(){
 
 $('#agentform').validate(
 {
  rules: {
    name: {
      minlength: 3,
      required: true
    },
    email: {
      required: true,
      email: true
    },
    interval: {
      number: true,
      required: true
    },
    start_at: {
      minlength: 1,
      required: true
    }
  },
  highlight: function(label) {
    $(label).closest('.control-group').addClass('error');
  },
  success: function(label) {
    label
      .text('OK!').addClass('valid')
      .closest('.control-group').addClass('success');
  }
 });

% for opt in options:
% if opt['type'] == 'string':
	$("#config_{{opt['name']}}").rules("add", { regex: /{{opt['regexp']}}/ })
% end
% if opt.get('required'):
$("#config_{{opt['name']}}").rules("add", { required: true })
% end
% end
 
}); // end document.ready
</script>
  </body>
  
  
<style>

label.valid {
  width: 24px;
  height: 24px;
  background: url(/public/img/valid.png) center center no-repeat;
  display: inline-block;
  text-indent: -9999px;
}
label.error {
  font-weight: bold;
  color: red;
  padding: 2px 8px;
  margin-top: 2px;
}
</style>
</html>
