ARG BUILD_FROM
FROM ${BUILD_FROM}

USER root

COPY --chmod=755 rootfs/run.sh /run.sh

ENTRYPOINT ["/run.sh"]
