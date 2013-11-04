%include templates/header title='Cloud Agents: Agent Configuration', custom="active"

<h2>Agent : {{agent['name']}}</h2>



% if get('error'):
<div class="alert alert-error">  
<strong>Error:</strong> {{error}}
</div>
% end

% if get('warning'):
<div class="alert alert-warning">  
<strong>Warning:</strong> {{warning}}
</div>
% end

<dl class="dl-horizontal">
  <dt>Name</dt>
  <dd>{{agent['name']}}</dd>
  <dt>Version</dt>
  <dd>{{agent['version']}}</dd>
  <dt>URL</dt>
  <dd><a href="{{agent['url']}}" target="_new">{{agent['url']}}</a></dd>
  <dt>Help</dt>
  <dd>{{agent['help']}}
  </dd>
</dl>

<h4>Configuration</h4>

<dl class="dl-horizontal">
% for opt in agent['options']:
  <dt>{{opt['title']}}</dt>
  <dd>{{opt['description']}}</dd>
% end
</dl>

<h4>Create New Task</h4>

<h5>General Settings</h5>

<form class="form-horizontal" action="/agent/create/" method="POST" id="agentform">
  <div class="control-group">
	<label class="control-label">Task Name</label>
	<div class="controls">
      <input type="text" 
        name="name" id="name"
      />
    </div>
  </div>
  <div class="control-group">
	<label class="control-label" for="interval">Interval</label>
	<div class="controls">
      <select name="interval" id="interval">
      <option value="0">Run Once
      <option value="60">1 Minute
      <option value="300">5 Minutes
      <option value="600">10 Minutes
      <option value="1800">30 Minutes
      <option value="3600">1 Hour
      <option value="10800">3 Hours
      <option value="21600">6 Hours
      <option value="43200">12 Hours
      <option value="86400">24 Hours
      <option value="604800">7 Days
	  </select>      
      <p class="help-block">Time between runs.</p>
    </div>
  </div>
  <div class="control-group">
	<label class="control-label" for="email">Email</label>
	<div class="controls">
      <input type="email" 
        data-validation-email-message="Must be a valid email address." 
        name="email" id="email"
      />
      <p class="help-block">Email address to send failure alerts and notifications to.</p>
    </div>
  </div>
  <div class="control-group">
	<label class="control-label">Start</label>
	<div class="controls">
	  <select name="start_at" id="start_at">
      <option value="0">Immediately
      <option value="+300">In 5 Minutes
      <option value="+600">In 10 Minutes
      <option value="+3600">In 1 Hour
      <option value="+21600">In 6 Hours
      <option value="+43200">In 12 Hours
	  </select>      
      <p class="help-block">Time to start task at.</p>
    </div>
  </div>
  <div class="control-group">
  <label class="control-label">Agent URL</label>
  <div class="controls">
      <input type="text" name="agent_url" readonly="readonly" value="{{agent['agent_url']}}" />
    <p class="help-block">Pre-filled for your convenience.</p>
  </div>
</div>

<h5>Agent Settings</h5>

% for opt in agent['options']:
  <div class="control-group">
	<label class="control-label" for="config_{{opt['name']}}">{{opt['title']}}</label>
	<div class="controls">
% if opt['type'] == 'boolean':
    <input type="checkbox" name="config-{{opt['name']}}" id="config_{{opt['name']}}" value="checkbox-true"
% if opt.get("default"):
% if opt['default']:
checked
% end
% end
    /> 
	<p class="help-block">{{opt['description']}}</p>

% elif opt['type'] == 'string':

% if opt.get('resource-select'):
      <select name="config-{{opt['name']}}" id="config_{{opt['name']}}">
         <option value="">Select One...
% for option in opt['resource-select']:
% print option
% name = option.get('name')
% value = option.get('value')
% if not option.get('value'):
         <option disabled="disabled">{{name}}
% else:
         <option value="{{value}}">{{name}}
% end
% end
      </select>

% else:
      <input type="text" name="config-{{opt['name']}}" id="config_{{opt['name']}}" />
% if not opt.get('required'):
(Optional)
% end

% end
% regexp = opt.get("regexp")
<p class="help-block">{{opt['description']}} 
% if regexp:
(Must match /{{regexp}}/)
% end
</p>

% elif opt['type'] == 'select':

      <select name="config-{{opt['name']}}" id="config_{{opt['name']}}">
         <option value="">Select One...
% for option in opt['options']:
% name = option.get('name')
% value = option.get('value')
         <option value="{{value}}"
% if option.get('default'):
default
% end

         >{{name}}
% end
      </select>
	<p class="help-block">{{opt['description']}}</p>
% end

    </div>
</div>
  
% end

<button type="submit" class="btn">Create</button>
</form>

%include templates/footer-agent-validation options=agent['options']
