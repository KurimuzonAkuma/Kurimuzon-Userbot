#!/usr/bin/env sh

if [ -x "$(command -v termux-setup-storage)" ]; then
    termux-wake-lock

    pkg update -y && pkg upgrade -y
    pkg install python3 git clang ffmpeg wget libjpeg-turbo libcrypt ndk-sysroot zlib openssl -y || exit 2

    python3 -m pip install -U pip
    export LDFLAGS="-L${PREFIX}/lib/"
    export CFLAGS="-I${PREFIX}/include/"
    pip3 install -U wheel
else
    if [ "$(id -u)" -ne 0 ]; then
        echo Please run this script as root
        exit 1
    fi

    apt update -y
    apt install python3 python3-pip git -y || exit 2
    python3 -m pip install -U pip wheel
fi



if [ -d "Kurimuzon-Userbot" ]; then
    cd Kurimuzon-Userbot || exit 2
    elif [ -f ".env.example" ] && [ -f "main.py" ] && [ -d "plugins" ]; then
    :
else
    git clone https://github.com/KurimuzonAkuma/Kurimuzon-Userbot || exit 2
    cd Kurimuzon-Userbot || exit 2
fi

if [ -f ".env" ] && [ -f "KurimuzonUserbot.session" ]; then
    printf "It seems that Kurimuzon-Userbot is already installed. Exiting...\n"
    exit
fi

python3 -m pip install -U -r requirements.txt || exit 2

echo
echo "Enter API_ID and API_HASH"
echo "You can get it here -> https://my.telegram.org/apps"
echo "Leave empty to use defaults (please note that default keys significantly increases your ban chances)"
printf "API_ID > "
read -r api_id

if [ "$api_id" = "" ]; then
    api_id="6"
    api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e"
else
    printf "API_HASH > "
    read -r api_hash
fi

echo
echo "Choose database settings:"
echo "[1] Enter name manually"
echo "[2] Use default name"
printf "> "
read -r db_settings

echo
case $db_settings in
    1)
        echo "Please enter database name with extension [database.db]:"
        printf "> "
        read -r db_name
    ;;
    *)
        db_name=database.db
    ;;
esac

cat > .env << EOL
API_ID=${api_id}
API_HASH=${api_hash}

# database name with extension.
DB_NAME=${db_name}
EOL



if [ -x "$(command -v termux-setup-storage)" ]; then
    echo
    echo "============================"
    echo "Great! Kurimuzon-Userbot installed successfully!"
    echo "Start with: \"python3 main.py\""
    echo "============================"
else
    chown -R "$SUDO_USER":"$SUDO_USER" .

    echo
    echo "Choose installation type:"
    echo "[1] Systemd service"
    echo "[2] PM2"
    echo "[3] Docker"
    echo "[4] Custom (default)"
    printf "> "
    read -r install_type

    case $install_type in
        1)
        cat > /etc/systemd/system/Kurimuzon-Userbot.service << EOL
    [Unit]
    Description=Service for Kurimuzon-Userbot
    [Service]
    Type=simple
    ExecStart=$(which python3) ${PWD}/main.py
    WorkingDirectory=${PWD}
    Restart=always
    RestartSec=5
    User=${SUDO_USER}
    Group=${SUDO_USER}
    [Install]
    WantedBy=multi-user.target
EOL
            if grep -qi microsoft /proc/version; then
                if grep -q systemd=true /etc/wsl.conf; then
                    :
                else
                    printf "[boot]\nsystemd=true" >> /etc/wsl.conf
                fi
            fi
            systemctl daemon-reload
            systemctl start Kurimuzon-Userbot
            systemctl enable Kurimuzon-Userbot

            echo
            echo "============================"
            echo "Great! Kurimuzon-Userbot installed successfully and running now!"
            echo "Installation type: Systemd service"
            printf "Start with: \e[0;36msudo systemctl start Kurimuzon-Userbot\e[0m"
            printf "Stop with: \e[0;36msudo systemctl start Kurimuzon-Userbot\e[0m"
            echo "============================"
        ;;
        2)
            if ! [ -x "$(command -v pm2)" ]; then
                curl -fsSL https://deb.nodesource.com/setup_19.x | bash
                apt install nodejs -y
                npm install pm2 -g
                su -c "pm2 startup" "$SUDO_USER"
                env PATH="$PATH":"/usr/bin /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u $SUDO_USER --hp /home/$SUDO_USER"
            fi
            su -c "pm2 start main.py --name KurimuzonUserbot --interpreter python3" "$SUDO_USER"
            su -c "pm2 save" "$SUDO_USER"

            echo
            echo "============================"
            echo "Great! Kurimuzon-Userbot installed successfully and running now!"
            echo "Installation type: PM2"
            printf "Start with: \e[0;36mpm2 start KurimuzonUserbot\e[0m"
            printf "Stop with: \e[0;36mpm2 stop KurimuzonUserbot\e[0m"
            echo "Process name: KurimuzonUserbot"
            echo "============================"
        ;;
        3)
            if ! [ -x "$(command -v docker-compose)" ]; then
                printf "\e[0;32mInstalling docker...\e[0m"
                if [ -f /etc/debian_version ]; then
                    sudo apt-get install \
                    apt-transport-https \
                    ca-certificates \
                    curl \
                    gnupg-agent \
                    software-properties-common -y
                    curl -fsSL https://download.docker.com/linux/ubuntu/gpg |
                    sudo apt-key add -
                    sudo add-apt-repository \
                    "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
                    $(lsb_release -cs) \
                    stable"
                    sudo apt-get update -y
                    sudo apt-get install docker-ce docker-ce-cli containerd.io -y
                    elif [ -f /etc/arch-release ]; then
                    sudo pacman -Syu docker --noconfirm
                    elif [ -f /etc/redhat-release ]; then
                    sudo yum install -y yum-utils
                    sudo yum-config-manager \
                    --add-repo \
                    https://download.docker.com/linux/centos/docker-ce.repo
                    sudo yum install docker-ce docker-ce-cli containerd.io -y
                fi
                printf "\e[0;32m - success\e[0m\n"
                printf "\e[0;32mInstalling docker-compose...\e[0m"
                pip install -U docker-compose
                chmod +x /usr/local/bin/docker-compose
                printf "\e[0;32m - success\e[0m\n"
            else
                printf "\e[0;32mDocker is already installed\e[0m\n"
            fi

            printf "\e[0;32mBuilding docker image...\e[0m"
            sudo docker-compose up -d --build
            printf "\e[0;32m - success\e[0m\n"

            container_id=$(docker ps | grep LostPicsShop | cut -d" " -f1)

            echo
            echo "============================"
            echo "Great! Kurimuzon-Userbot installed successfully!"
            echo "Installation type: Docker"
            printf 'Start with: \e[0;36mdocker start %s\e[0m' "$container_id"
            printf 'Stop with: \e[0;36mdocker stop %s\e[0m' "$container_id"
            echo "Process name: KurimuzonUserbot"
            echo "============================"
            printf '\e[0;31mAttach to docker container to continue installation using: \e[0;36mdocker attach %s\e[0m\n' "$container_id"
        ;;
        *)
            echo
            echo "============================"
            echo "Great! Kurimuzon-Userbot installed successfully!"
            echo "Installation type: Custom"
            echo "Start with: \"python3 main.py\""
            echo "============================"
        ;;
    esac
fi
