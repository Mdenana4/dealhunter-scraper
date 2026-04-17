FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV ANDROID_HOME=/opt/android-sdk
ENV FLUTTER_HOME=/opt/flutter
ENV PATH=$PATH:$FLUTTER_HOME/bin:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/tools/bin

RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    unzip \
    openjdk-17-jdk \
    && rm -rf /var/lib/apt/lists/*

# Install Android SDK
RUN mkdir -p $ANDROID_SDK_ROOT/cmdline-tools && \
    cd /tmp && \
    wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip && \
    unzip -q commandlinetools-linux-11076708_latest.zip && \
    mv cmdline-tools $ANDROID_SDK_ROOT/cmdline-tools/latest && \
    rm commandlinetools-linux-11076708_latest.zip

RUN yes | $ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager --sdk_root=$ANDROID_SDK_ROOT \
    "platforms;android-34" \
    "build-tools;34.0.0" \
    "platform-tools" 2>&1 | grep -v "Warning"

# Install Flutter
RUN git clone https://github.com/flutter/flutter.git $FLUTTER_HOME && \
    cd $FLUTTER_HOME && \
    git checkout 3.19.0 && \
    flutter config --no-analytics && \
    flutter config --android-sdk $ANDROID_SDK_ROOT && \
    flutter doctor

WORKDIR /app
COPY . .

RUN cd app/admin_app && \
    flutter clean && \
    flutter pub get --verbose && \
    flutter build apk --release 2>&1 | tee build.log

CMD ["bash", "-c", "if [ -f app/admin_app/build/app/outputs/flutter-apk/app-release.apk ]; then ls -lh app/admin_app/build/app/outputs/flutter-apk/app-release.apk; else cat app/admin_app/build.log; fi"]
