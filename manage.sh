#!/bin/bash

function start_core() {
    docker compose up -d
}

function stop_core() {
    docker compose down
}

function list_plugins() {
    echo "Available plugins:"
    ls plugins/
}

function start_plugin() {
    if [ -z "$1" ]; then
        echo "Please specify a plugin name"
        return 1
    fi
    
    if [ ! -d "plugins/$1" ]; then
        echo "Plugin $1 not found"
        return 1
    fi
    
    echo "Starting plugin $1..."
    cd plugins/$1
    docker compose up -d
    cd ../..
}

function stop_plugin() {
    if [ -z "$1" ]; then
        echo "Please specify a plugin name"
        return 1
    fi
    
    if [ ! -d "plugins/$1" ]; then
        echo "Plugin $1 not found"
        return 1
	fi
    
    echo "Stopping plugin $1..."
    cd plugins/$1
    docker compose down
    cd ../..
}

function start_all() {
    start_core
    for plugin in plugins/*; do
        if [ -d "$plugin" ]; then
            plugin_name=$(basename "$plugin")
            start_plugin "$plugin_name"
        fi
    done
}

function stop_all() {
    for plugin in plugins/*; do
        if [ -d "$plugin" ]; then
            plugin_name=$(basename "$plugin")
            stop_plugin "$plugin_name"
        fi
    done
    stop_core
}

case "$1" in
    "start-core")
        start_core
        ;;
    "stop-core")
        stop_core
        ;;
    "list-plugins")
        list_plugins
        ;;
    "start-plugin")
        start_plugin "$2"
        ;;
    "stop-plugin")
        stop_plugin "$2"
        ;;
    "start-all")
        start_all
        ;;
    "stop-all")
        stop_all
        ;;
    *)
        echo "Usage: $0 {start-core|stop-core|list-plugins|start-plugin <name>|stop-plugin <name>|start-all|stop-all}"
        exit 1
        ;;
esac
