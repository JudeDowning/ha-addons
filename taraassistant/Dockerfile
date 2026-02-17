ARG BUILD_FROM
FROM ${BUILD_FROM}

COPY rootfs/run.sh /run.sh
RUN chmod a+x /run.sh

ENTRYPOINT ["/run.sh"]
