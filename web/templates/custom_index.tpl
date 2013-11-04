%include templates/header title='Cloud Agents: Custom Agent', custom="active"

<h2><a href="/custom">Custom Agent</a></h2>

% if get('error'):
<div class="alert alert-error">  
<strong>Error:</strong> {{error}}
</div>
% end

<p>Agents can be loaded from HTTP or HTTPS urls, as well as Cloud Storage.  The cloud storage url format is:</p>

<code>
swift://region/container/object
</code>

<p>So a region-a.geo-1 container named agents with a script of testagents/debug.py would be:</p>

<code>
swift://region-a.geo-1/agents/testagents/debug.py
</code>

<p>

<form class="form-horizontal" action="/agent/show/" method="POST" id="agentform">
  <div class="control-group">
	<label class="control-label">Agent URL</label>
	<div class="controls">
      <input type="text" 
        name="url" id="url"
      />
    </div>
  </div>

<button type="submit" class="btn">Configure</button>
</form>

%include templates/footer
