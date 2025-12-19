# aptner
Home Assistant - Aptner Component

![Aptner Logo](images/logo.png)

Aptner Integration for Home Assistant
https://img.shields.io/badge/HACS-Custom-orange.svg

한국 아파트 관리 서비스 '아파트너(Aptner)'의 주차 관리 및 관리비 정보를 Home Assistant에 통합합니다.

주요 기능
차량 위치 추적: 옵션에 등록된 차량의 주차 상태 실시간 확인

관리비 조회: 월별 관리비 금액 및 상세 내역 확인

방문차량 예약: 예약 현황 조회 및 새로운 예약 기능

주차 기록: 차량 입출차 기록 확인

설치 방법
HACS를 통한 설치 (권장)
HACS → 통합구성요소 → 오른쪽 상단 메뉴 (⋮) → 사용자 지정 저장소

저장소 URL에 https://github.com/사용자명/저장소명 입력

"통합구성요소" 카테고리 선택

저장소 추가 후 Aptner 검색 및 설치

Home Assistant 재시작

수동 설치
custom_components 폴더에 aptner 폴더 복사

Home Assistant 재시작

설정 → 통합구성요소 → "통합구성요소 추가" → "Aptner" 검색

설정
초기 설정
아파트너 계정 정보 입력

ID: 아파트너 로그인 ID

비밀번호: 아파트너 로그인 비밀번호

옵션 설정 (통합구성요소 옵션에서 설정 가능)

차량번호: 추적할 차량 번호 (쉼표로 구분, 예: 12가3456,34나5678)

스캔 간격: 데이터 업데이트 주기 (기본: 2분, 범위: 2-1440분)

생성되는 엔티티
센서
sensor.aptner_관리비: 현재 관리비 금액 및 상세 내역

sensor.aptner_방문차량_예약현황: 전체 예약 현황

장치 추적기 (Device Tracker)
device_tracker.aptner_차량번호: 각 차량의 주차 상태

home: 주차장에 있음 (주차 중)

not_home: 주차장에 없음 (외출 중)

서비스
aptner.fee
관리비 정보 조회

aptner.findcar
차량 입출차 기록 조회

필드:

carno (선택사항, 특정 차량번호)

aptner.get_car_status
차량 현재 주차 상태 조회 (device_tracker용)

필드:

entry_id (선택사항, 다중 계정 시)

carno (선택사항, 특정 차량번호)

aptner.get_reserve_status
방문차량 예약 현황 조회

aptner.reserve_car
방문차량 주차 예약

필드:

date: 방문시작일 (형식: 2025.01.01)

purpose: 방문목적

carno: 차량번호

days: 방문기간 (일)

phone: 연락처

자동화 예시
차량이 집에 도착하면 알림 보내기
yaml
automation:
  - alias: "차량 도착 알림"
    trigger:
      platform: state
      entity_id: device_tracker.aptner_12가3456
      from: "not_home"
      to: "home"
    action:
      service: notify.mobile_app
      data:
        message: "차량이 주차장에 도착했습니다."
관리비가 나오면 알림
yaml
automation:
  - alias: "관리비 알림"
    trigger:
      platform: state
      entity_id: sensor.aptner_관리비
    action:
      service: notify.mobile_app
      data:
        message: "이번 달 관리비는 {{ states('sensor.aptner_관리비') }}원 입니다."
매월 1일 관리비 확인
yaml
automation:
  - alias: "월초 관리비 확인"
    trigger:
      platform: time
      at: "00:05:00"
      day_of_month: 1
    action:
      service: aptner.fee
차량이 외출 중일 때 조명 켜기
yaml
automation:
  - alias: "차량 외출 시 조명 켜기"
    trigger:
      platform: state
      entity_id: device_tracker.aptner_12가3456
      from: "home"
      to: "not_home"
    action:
      service: light.turn_on
      target:
        entity_id: light.living_room
Lovelace 대시보드 카드 예시
차량 상태 카드
yaml
type: entities
title: 차량 상태
entities:
  - entity: device_tracker.aptner_12가3456
    name: 내 차
  - entity: device_tracker.aptner_34나5678
    name: 배우자 차
관리비 카드
yaml
type: glance
title: 아파트 관리
entities:
  - entity: sensor.aptner_관리비
    name: 관리비
  - entity: sensor.aptner_방문차량_예약현황
    name: 예약 현황
문제 해결
일반적인 문제
인증 실패: ID/비밀번호를 확인해주세요.

차량 상태 업데이트 안됨: 스캔 간격을 확인하고 로그를 확인해주세요.

엔티티가 생성되지 않음: 통합구성요소 재설치 시도

로그 확인
yaml
logger:
  default: warning
  logs:
    custom_components.aptner: debug
자주 묻는 질문
Q: 차량 상태가 제대로 업데이트되지 않아요
A: 아파트너 시스템의 데이터 업데이트 주기에 따라 약간의 지연이 있을 수 있습니다. 스캔 간격을 조정해보세요.

Q: 여러 대의 차량을 등록할 수 있나요?
A: 네, 옵션에서 쉼표로 구분하여 여러 차량번호를 입력할 수 있습니다.

Q: 다른 아파트너 계정도 추가할 수 있나요?
A: 네, 별도의 통합구성요소로 추가할 수 있습니다.

기여하기
버그 리포트나 기능 요청은 GitHub Issues를 이용해주세요.

개발 환경 설정
bash
# 저장소 클론
git clone https://github.com/사용자명/저장소명.git

# 개발 브랜치 생성
git checkout -b feature/new-feature
라이선스
이 프로젝트는 MIT 라이선스 하에 배포됩니다.

text
MIT License

Copyright (c) 2024 [사용자명]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
버전 기록
v0.4.0 (현재)
차량 트래커(device_tracker) 기능 추가

isExit 값에 따른 home/not_home 상태 지원

차량별 주차 상태 실시간 모니터링

v0.3.0
기본 관리비 및 예약 기능 구현

서비스: fee, findcar, get_reserve_status, reserve_car

v0.2.0
초기 릴리즈

기본 인증 및 설정 흐름 구현

연락처
GitHub: 사용자명/저장소명

이슈 트래커: Issues

Home Assistant 커뮤니티: 포럼

지원
이 통합구성요소는 커뮤니티에 의해 개발 및 유지됩니다.
도움이 필요하시면 GitHub Issues를 통해 문의해주세요.

면책 조항: 이 통합구성요소는 공식 아파트너 제품이 아닙니다. 아파트너 API 변경 시 기능이 작동하지 않을 수 있습니다. 이 소프트웨어는 어떠한 보증 없이 "있는 그대로" 제공됩니다.
