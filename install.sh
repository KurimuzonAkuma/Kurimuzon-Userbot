#!/usr/bin/env sh

if [ -x "$(command -v termux-setup-storage)" ]; then
    termux-wake-lock

    pkg update -y && pkg upgrade -y
    pkg install python3 git clang ffmpeg wget libjpeg-turbo libcrypt ndk-sysroot zlib openssl -y || exit 2

    python3 -m pip install -U pip
    LDFLAGS="-L${PREFIX}/lib/"
    CFLAGS="-I${PREFIX}/include/"
    pip3 install -U wheel
else
    if [ $(id -u) -ne 0 ]; then
    echo Please run this script as root
    exit 1
    fi

    apt update -y
    apt install python3 python3-pip git -y || exit 2
    python3 -m pip install -U pip wheel
fi



if [ -d "Kurimuzon-Userbot" ]; then
  cd Kurimuzon-Userbot
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
echo "Leave empty to use defaults"
read -r -p "API_ID > " api_id

if [ "$api_id" = "" ]; then
  api_id="6"
  api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e"
else
  read -r -p "API_HASH > " api_hash
fi

echo
echo "Choose database settings:"
echo "[1] Enter name manually"
echo "[2] Use default name"
read -r -p "> " db_settings

echo
case $db_settings in
  1)
    echo "Please enter database name with extension [database.db]:"
    read -r -p "> " db_name
    db_name=$db_name
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
    echo "Great! Dragon-Userbot installed successfully!"
    echo "Start with: \"python3 main.py\""
    echo "============================"
else
    chown -R $SUDO_USER:$SUDO_USER .

    echo
    echo "Choose installation type:"
    echo "[1] Systemd service"
    echo "[2] Custom (default)"
    read -r -p "> " install_type

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
                echo "[boot]\nsystemd=true" >> /etc/wsl.conf
            fi
        fi
        systemctl daemon-reload
        systemctl start Kurimuzon-Userbot
        systemctl enable Kurimuzon-Userbot

        echo
        echo "============================"
        echo "Great! Kurimuzon-Userbot installed successfully and running now!"
        echo "Installation type: Systemd service"
        echo "Start with: \"sudo systemctl start Kurimuzon-Userbot\""
        echo "Stop with: \"sudo systemctl stop Kurimuzon-Userbot\""
        echo "============================"
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
