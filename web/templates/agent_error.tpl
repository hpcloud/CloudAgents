%include templates/header title='Cloud Agents: Agent Error'), agents="active"

<h2>Agents: Error</h2>



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


%include templates/footer-agent-validation options=agent['options']
