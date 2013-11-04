<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
	<title>{{title or 'Untitled'}}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="">
    <meta name="author" content="">

    <!-- Le styles -->
    <link href="/public/bootstrap/css/bootstrap.css" rel="stylesheet">
    <style>
      body {
        padding-top: 60px; /* 60px to make the container go all the way to the bottom of the topbar */
      }
    </style>
    <link href="/public/bootstrap/css/bootstrap-responsive.css" rel="stylesheet">

    <!-- Le HTML5 shim, for IE6-8 support of HTML5 elements -->
    <!--[if lt IE 9]>
      <script src="http://html5shim.googlecode.com/svn/trunk/html5.js"></script>
    <![endif]-->

    <!-- Le fav and touch icons -->
    <link rel="shortcut icon" href="/public/bootstrap/ico/favicon.ico">
    <link rel="apple-touch-icon-precomposed" sizes="144x144" href="/public/bootstrap/ico/apple-touch-icon-144-precomposed.png">
    <link rel="apple-touch-icon-precomposed" sizes="114x114" href="/public/bootstrap/ico/apple-touch-icon-114-precomposed.png">
    <link rel="apple-touch-icon-precomposed" sizes="72x72" href="/public/bootstrap/ico/apple-touch-icon-72-precomposed.png">
    <link rel="apple-touch-icon-precomposed" href="/public/bootstrap/ico/apple-touch-icon-57-precomposed.png">
    <script src="/public/bootstrap/js/jquery.js"></script>

  </head>

  <body>
    <div class="navbar navbar-inverse navbar-fixed-top">
      <div class="navbar-inner">
        <div class="container">
          <a class="btn btn-navbar" data-toggle="collapse" data-target=".nav-collapse">
            <span class="icon-bar"></span>
            <span class="icon-bar"></span>
            <span class="icon-bar"></span>
          </a>
          <a class="brand" href="/">Cloud Agents</a>
% if defined('logged_in'):
%   if logged_in == False:
%     pass
%   end
% else:
          <div class="nav-collapse collapse">
            <ul class="nav">
              <li class="{{get("tasks")}}"><a href="/tasks">Tasks</a></li>
              <li class="{{get("agents")}}"><a href="/agents">Agents</a></li>
              <li class="{{get("custom")}}"><a href="/custom">Custom Agents</a></li>
              <li class="{{get("accesskeys")}}"><a href="/accesskeys">Access Keys</a></li>
            </ul>
            <ul class="nav pull-right">
              <li><a href="/logout">Logout</a></li>
            </ul>
% end
          </div><!--/.nav-collapse -->
        </div>
      </div>
    </div>

    <div class="container">
