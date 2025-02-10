#!/bin/bash

# 检查插件目录是否存在
function check_plugins() {
    if [ ! -d "plugins" ]; then
        echo "Creating plugins directory..."
        mkdir plugins
    fi
}

# 列出所有插件
function list_plugins() {
    echo "Available plugins:"
    ls -1 plugins/
}

# 启动核心服务
function start_core() {
    echo "Starting core services..."
    docker compose up -d
}

# 停止核心服务
function stop_core() {
    echo "Stopping core services..."
    docker compose down
}

# 启动指定插件
function start_plugin() {
    local plugin=$1
    if [ -z "$plugin" ]; then
        echo "Please specify a plugin name"
        exit 1
    fi
    
    if [ ! -d "plugins/$plugin" ]; then
        echo "Plugin $plugin not found"
        exit 1
    fi
    
    echo "Starting plugin $plugin..."
    cd "plugins/$plugin" && docker compose up -d
    cd ../..
}

# 停止指定插件
function stop_plugin() {
    local plugin=$1
    if [ -z "$plugin" ]; then
        echo "Please specify a plugin name"
        exit 1
    fi
    
    if [ ! -d "plugins/$plugin" ]; then
        echo "Plugin $plugin not found"
        exit 1
    fi
    
    echo "Stopping plugin $plugin..."
    cd "plugins/$plugin" && docker compose down
    cd ../..
}

# 启动所有服务
function start_all() {
    start_core
    for plugin in plugins/*; do
        if [ -d "$plugin" ]; then
            start_plugin $(basename "$plugin")
        fi
    done
}

# 停止所有服务
function stop_all() {
    for plugin in plugins/*; do
        if [ -d "$plugin" ]; then
            stop_plugin $(basename "$plugin")
        fi
    done
    stop_core
}

# 清理所有容器
function clean_all() {
    echo "Cleaning up all containers..."
    docker compose down --remove-orphans
    for plugin in plugins/*; do
        if [ -d "$plugin" ]; then
            cd "$plugin" && docker compose down --remove-orphans
            cd ../..
        fi
    done
}

# 重建核心服务
function rebuild_core() {
    echo "Rebuilding core services..."
    docker compose build tts-controller
}

# 重建指定插件
function rebuild_plugin() {
    local plugin=$1
    if [ -z "$plugin" ]; then
        echo "Please specify a plugin name"
        exit 1
    fi
    
    if [ ! -d "plugins/$plugin" ]; then
        echo "Plugin $plugin not found"
        exit 1
    fi
    
    echo "Rebuilding plugin $plugin..."
    cd "plugins/$plugin" && docker compose build
    cd ../..
}

# 重建所有服务
function rebuild_all() {
    echo "Rebuilding all services..."
    rebuild_core
    
    echo "Rebuilding plugins..."
    for plugin in plugins/*; do
        if [ -d "$plugin" ]; then
            rebuild_plugin $(basename "$plugin")
        fi
    done
    
    echo "Restarting all services..."
    clean_all
    start_all
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
    "clean")
        clean_all
        ;;
    "rebuild-core")
        rebuild_core
        clean_all
        start_core
        ;;
    "rebuild-plugin")
        rebuild_plugin "$2"
        stop_plugin "$2"
        start_plugin "$2"
        ;;
    "rebuild-all")
        rebuild_all
        ;;
    *)
        echo "Usage: $0 {start-core|stop-core|list-plugins|start-plugin <n>|stop-plugin <n>|start-all|stop-all|clean|rebuild-core|rebuild-plugin <n>|rebuild-all}"
        exit 1
        ;;
esac
